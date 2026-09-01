"""
감사 — 발행 전에 카탈로그의 구멍과 중복을 찾는다.

  1) 음원이 안 붙은 트랙 (album.md 에는 있는데 mp3 가 없음)
  2) 내용이 완전히 같은 중복 음원 (폴더명이 달라도 잡는다)
  3) 가사가 비어 있는 트랙 (연주곡 제외)

지우지 않는다. 목록만 낸다 — 무엇을 지울지는 사람이 판단할 일이다.

사용법:
    python scripts/jukebox/audit.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"


def fingerprint(path: Path) -> str:
    """크기 + 앞뒤 1MB 해시. 전체를 읽지 않고도 동일 파일을 사실상 확정할 수 있다."""
    size = path.stat().st_size
    h = hashlib.sha256(str(size).encode())
    with path.open("rb") as f:
        h.update(f.read(1 << 20))
        if size > (2 << 20):
            f.seek(-(1 << 20), 2)
            h.update(f.read(1 << 20))
    return h.hexdigest()


def main() -> int:
    albums = json.loads(CATALOG.read_text(encoding="utf-8"))

    no_audio, no_lyrics = [], []
    prints: dict[str, list[tuple[str, str, int]]] = defaultdict(list)

    for a in albums:
        for t in a["tracks"]:
            label = (a["folder"], t["title"], t["n"])
            if not t.get("src") or not Path(t["src"]).exists():
                no_audio.append(label)
                continue
            if not t.get("lyrics") and not t.get("instrumental"):
                no_lyrics.append(label)
            prints[fingerprint(Path(t["src"]))].append(label)

    dupes = {k: v for k, v in prints.items() if len(v) > 1}
    dup_tracks = sum(len(v) - 1 for v in dupes.values())

    print("═══ 발행 전 감사 ═══")
    print(f"앨범 {len(albums)}개 · 트랙 {sum(len(a['tracks']) for a in albums)}곡\n")

    print(f"① 음원 없는 트랙 {len(no_audio)}곡")
    by_album: dict[str, int] = defaultdict(int)
    for folder, _, _ in no_audio:
        by_album[folder] += 1
    for folder, n in sorted(by_album.items(), key=lambda x: -x[1]):
        print(f"     {folder:30s} {n}곡")

    print(f"\n② 내용이 같은 중복 음원 {len(dupes)}묶음 (중복분 {dup_tracks}곡)")
    for grp in list(dupes.values())[:15]:
        head = f"{grp[0][0]} #{grp[0][2]} {grp[0][1][:26]}"
        rest = ", ".join(f"{g[0]} #{g[2]}" for g in grp[1:])
        print(f"     {head}  ==  {rest}")
    if len(dupes) > 15:
        print(f"     … 외 {len(dupes)-15}묶음")

    print(f"\n③ 가사 없는 트랙(연주곡 제외) {len(no_lyrics)}곡")
    by_album2: dict[str, int] = defaultdict(int)
    for folder, _, _ in no_lyrics:
        by_album2[folder] += 1
    for folder, n in sorted(by_album2.items(), key=lambda x: -x[1])[:10]:
        print(f"     {folder:30s} {n}곡")

    print("\n※ 아무것도 지우지 않았습니다. 발행 시 음원 없는 트랙은 자동으로 제외됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
