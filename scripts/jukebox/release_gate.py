"""유튜브에 공개된 앨범만 자동 발행하게 거르는 문.

주크박스는 input/ 폴더를 보고 발행하므로, 사람이 없는 자동 실행에서는 아직 안 올린 앨범까지
공개될 수 있다. public/data.js 는 API 키로 받은 공개 영상 목록이라(비공개·예약 영상은 안 잡힌다)
여기에 앨범이 보이면 공개된 것으로 본다.

사람이 직접 치는 /jukebox·run_all.py 는 지금까지처럼 이 문을 거치지 않는다.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import _env
from yt_match import norm, station_from_hint

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CATALOG = HERE / "catalog.json"
DATA_JS = REPO / "public" / "data.js"
SKIP_MARKER = ".nojukebox"


def load_videos() -> list[dict]:
    text = DATA_JS.read_text(encoding="utf-8")
    m = re.search(r"SITE_DATA_B64\s*=\s*['\"]([^'\"]+)", text)
    if not m:
        raise RuntimeError("public/data.js 에서 영상 목록을 읽지 못했습니다")
    data = json.loads(base64.b64decode(m.group(1)).decode("utf-8"))
    items = data if isinstance(data, list) else (data.get("albums") or data.get("items") or [])
    return [x for x in items if x.get("source") == "youtube-api"]


def published_folders() -> set[str]:
    """이미 발행된 앨범 폴더. 이 앨범들은 문을 다시 통과할 필요가 없다."""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    albums = data.get("albums", []) if isinstance(data, dict) else data
    return {a["folder"] for a in albums}


def name_keys(title: str) -> set[str]:
    """영상 제목에서 찾을 앨범 이름들. 괄호 안 쉼표로 쪼개지 않는다
    ('Morning Hymns, Vol. 2' 를 쪼개면 Vol. 1 영상에도 걸린다)."""
    title = re.sub(r"\s+[—–]\s+.*$", "", title).strip()
    names = {title}
    m = re.match(r"^(.*?)\s*[(\[（](.*)[)\]）]\s*$", title)
    if m:
        names |= {m.group(1), m.group(2)}
    keys = set()
    for name in names:
        key = norm(name)
        # 'Live' 같은 짧은 영문 단어가 아무 영상에나 걸리지 않게 영문은 더 길게 요구한다
        if len(key) >= (6 if key.isascii() else 4):
            keys.add(key)
    return keys


def is_released(title: str, channel_hint: str, videos: list[dict]) -> bool:
    keys = name_keys(title)
    station = station_from_hint(channel_hint)
    for video in videos:
        if station and video.get("genre") != station:
            continue
        video_title = norm(str(video.get("title", "")))
        if any(key in video_title for key in keys):
            return True
    return False


def read_album_md(folder: Path) -> tuple[str, str] | None:
    """(앨범 제목, 채널 표기). album.md 가 없으면 None."""
    mds = sorted(folder.glob("*album*.md"))
    if not mds:
        return None
    md = max(mds, key=lambda p: p.stat().st_mtime)
    text = md.read_text(encoding="utf-8", errors="replace")
    title = re.sub(r"^\s*Album\s*[:：]\s*", "", text.split("\n", 1)[0].lstrip("# ").strip())
    m = re.search(r"^\*\*Channel\*\*\s*[:：]\s*(.+)$", text, re.M)
    return title, (m.group(1).strip() if m else "")


def has_audio(folder: Path) -> bool:
    return any(re.match(r"\d+", f.name) for f in folder.rglob("*.mp3"))


def split_new_albums() -> tuple[list[str], list[str]]:
    """아직 발행 안 된 앨범을 (유튜브 공개됨, 아직 안 보임) 폴더명으로 나눈다."""
    videos = load_videos()
    known = published_folders()
    ready, waiting = [], []
    for folder in sorted(p for p in _env.input_dir().iterdir() if p.is_dir()):
        if folder.name in known or (folder / SKIP_MARKER).exists() or not has_audio(folder):
            continue
        info = read_album_md(folder)
        if info is None:
            continue
        (ready if is_released(*info, videos) else waiting).append(folder.name)
    return ready, waiting


if __name__ == "__main__":
    ready, waiting = split_new_albums()
    print(f"발행 대상(유튜브 공개됨) {len(ready)}개: {', '.join(ready)}")
    print(f"대기(유튜브에 아직 없음) {len(waiting)}개: {', '.join(waiting)}")
