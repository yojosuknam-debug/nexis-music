"""
텔레그램 `/jukebox` 실행기 — 미니PC 의 봇이 이 파일을 부른다.

봇 코드에는 **얇은 갈래 하나만** 붙이고, 실제 일은 전부 여기서 한다.
그래야 이쪽이 어떻게 깨지든 봇의 다른 명령(/run, /track, /shorts …)은 멀쩡하다.

    from jukebox_bridge import run_jukebox   # 봇 쪽 얇은 어댑터
    run_jukebox(send_message)

동작:
    git pull  →  scan  →  assets  →  upload  →  pages  →  commit/push
    (미니PC 는 앨범 원본이 있는 기계라 동기화 단계가 자동으로 빠진다)

안전장치:
    * 모든 예외를 잡아 텔레그램으로 알린다. 봇 프로세스를 죽이지 않는다.
    * 중복 실행 방지 — 이미 돌고 있으면 즉시 거절한다.
    * 단계별 제한시간. 매달려 있으면 끊고 보고한다.
    * 코드가 바뀌었을 수 있으므로 실행 전 git pull 로 최신을 당겨온다.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

REPO = Path("/mnt/external/nexis-music")
PY = "/home/yojosuknam/suno-venv/bin/python"
SITE = "https://music.yojosuknam.com/album"

_lock = threading.Lock()
_running = False

# (표시이름, 인자, 제한시간초, 실패해도 계속할지)
STEPS = [
    ("카탈로그 수집", ["scripts/jukebox/scan_albums.py"], 900, False),
    ("커버 준비", ["scripts/jukebox/prepare_assets.py"], 900, False),
    ("R2 업로드", ["scripts/jukebox/upload_r2.py"], 5400, False),
    ("페이지 생성", ["scripts/jukebox/build_pages.py"], 900, False),
]


def _run(args: list[str], timeout: int) -> tuple[bool, str]:
    try:
        r = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"제한시간 {timeout//60}분 초과"
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    return r.returncode == 0, "\n".join(tail[-6:])


def _work(send) -> None:
    global _running
    t0 = time.time()
    try:
        send("🎧 주크박스 갱신 시작…")

        # 지난 실행이 남긴 생성물(카탈로그·커버) 변경을 먼저 되돌린다.
        # 그러지 않으면 pull 이 "local changes would be overwritten" 으로 막혀
        # 코드가 영영 낡은 채로 돈다(2026-09-02 실제 발생).
        _run(["git", "checkout", "--", "scripts/jukebox/catalog.json",
              "scripts/jukebox/assets"], 60)
        ok, out = _run(["git", "pull", "--ff-only", "-q"], 180)
        if not ok:
            send(f"⚠️ 코드 최신화 실패 — 그대로 진행합니다\n{out[:200]}")

        for name, args, limit, lenient in STEPS:
            ok, out = _run([PY, *args], limit)
            if not ok and not lenient:
                send(f"❌ '{name}' 단계에서 멈췄습니다.\n\n{out[:600]}\n\n"
                     "사이트는 이전 상태 그대로입니다.")
                return
            send(f"✅ {name}\n{out[:400]}")

        # 변경이 없으면 커밋하지 않는다
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                            capture_output=True, text=True).stdout.strip()
        if not st:
            send(f"변경 사항이 없습니다. 이미 최신입니다.\n{SITE}")
            return

        n = len(list((REPO / "public" / "album").glob("*.html"))) - 1
        subprocess.run(["git", "add", "-A"], cwd=str(REPO), check=True)
        subprocess.run(["git", "commit", "-q", "-m",
                        f"chore(jukebox): 앨범 갱신 — 페이지 {n}장 (텔레그램 /jukebox)"],
                       cwd=str(REPO), check=True)
        ok, out = _run(["git", "push", "-q", "origin", "master"], 300)
        if not ok:
            send(f"⚠️ 푸시 실패 — 커밋은 되어 있습니다.\n{out[:300]}")
            return

        send(f"🚀 완료 — 앨범 페이지 {n}장\n{SITE}\n"
             f"(배포 반영까지 1~2분 · 총 {int(time.time()-t0)//60}분 걸림)")

    except Exception as e:                       # 무슨 일이 있어도 봇은 살아 있어야 한다
        send(f"❌ 주크박스 갱신 중 예외: {type(e).__name__}: {str(e)[:300]}")
    finally:
        with _lock:
            _running = False


def run_jukebox(send) -> None:
    """봇에서 부르는 진입점. 즉시 반환하고 백그라운드로 진행한다."""
    global _running
    with _lock:
        if _running:
            send("이미 주크박스 갱신이 돌고 있습니다. 끝나면 알려드립니다.")
            return
        if not REPO.exists():
            send(f"❌ 레포가 없습니다: {REPO}")
            return
        _running = True
    threading.Thread(target=_work, args=(send,), daemon=True).start()
