"""
주크박스 일괄 갱신 — 이 한 줄이면 끝난다.

    python scripts/jukebox/run_all.py

유튜브에 앨범을 올린 뒤 "주크박스에 반영해줘" 하면 이걸 돌린다.
미니PC에서 새 앨범을 받아오는 것부터 배포까지 전 과정을 순서대로 실행한다.
각 단계는 재실행 안전하다 — 이미 처리된 앨범은 알아서 건너뛴다.

    0 sync    미니PC → 데스크탑, 새 앨범만
    1 scan    album.md·mp3 → catalog.json
    2 assets  커버 확보(유튜브 썸네일 / 없으면 타이포 생성)
    3 upload  R2 업로드(크기 같으면 건너뜀)
    4 pages   Aurora Glass 페이지 생성
      audit   구멍·중복 검사 (보고만, 실패시켜도 진행)

옵션:
    --skip-sync   미니PC를 건너뛴다(꺼져 있을 때)
    --no-push     커밋·푸시하지 않는다(결과만 확인)
    --dry-run     각 단계가 무엇을 할지만 본다
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = sys.executable


def step(title: str, args: list[str], optional: bool = False) -> bool:
    print(f"\n{'─'*62}\n▶ {title}\n{'─'*62}", flush=True)
    t0 = time.time()
    r = subprocess.run([PY, *args], cwd=str(REPO))
    dt = time.time() - t0
    if r.returncode != 0:
        mark = "⚠️ 실패(계속 진행)" if optional else "❌ 실패 — 중단합니다"
        print(f"{mark}  [{dt:.0f}초]")
        return optional
    print(f"✅ 완료  [{dt:.0f}초]")
    return True


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sync", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = ["--dry-run"] if a.dry_run else []

    # 미니PC 는 앨범 원본이 있는 기계라 받아올 곳이 없다
    if _env.is_source_host():
        print("(원본 기계에서 실행 중 — 동기화 단계 생략)")
    elif not a.skip_sync:
        if not step("0/4 미니PC에서 새 앨범 받기", ["scripts/jukebox/sync_from_minipc.py", *d],
                    optional=True):
            return 1
    if not step("1/4 카탈로그 수집", ["scripts/jukebox/scan_albums.py"]):
        return 1
    if not step("2/4 커버 준비", ["scripts/jukebox/prepare_assets.py"]):
        return 1
    if not step("3/4 R2 업로드", ["scripts/jukebox/upload_r2.py", *d]):
        return 1
    if a.dry_run:
        print("\n(--dry-run: 페이지 생성·배포는 하지 않았습니다)")
        return 0
    if not step("4/4 페이지 생성", ["scripts/jukebox/build_pages.py"]):
        return 1
    step("검사 (보고용)", ["scripts/jukebox/audit.py"], optional=True)

    # ── 배포 ──────────────────────────────────────────────────────────────
    changed = git("status", "--porcelain")
    if not changed:
        print("\n변경 사항이 없습니다. 이미 최신 상태입니다.")
        return 0

    n_pages = len(list((REPO / "public" / "album").glob("*.html"))) - 1
    print(f"\n변경된 파일 {len(changed.splitlines())}개 · 앨범 페이지 {n_pages}장")
    if a.no_push:
        print("(--no-push: 커밋하지 않았습니다. `git status` 로 확인하세요)")
        return 0

    subprocess.run(["git", "add", "-A"], cwd=str(REPO), check=True)
    msg = (f"chore(jukebox): 앨범 갱신 — 페이지 {n_pages}장\n\n"
           f"scripts/jukebox/run_all.py 자동 실행 결과.\n\n"
           f"Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>")
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=str(REPO), check=True)
    r = subprocess.run(["git", "push", "-q", "origin", "master"], cwd=str(REPO))
    if r.returncode != 0:
        print("⚠️ 푸시 실패 — 커밋은 되어 있습니다. 수동으로 `git push` 하세요.")
        return 1
    print(f"\n🚀 배포됨 — https://music.yojosuknam.com/album (Vercel 반영까지 1~2분)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
