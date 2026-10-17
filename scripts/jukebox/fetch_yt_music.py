"""
곡별 유튜브 링크 재료를 받아 assets/ 에 저장한다. build_pages.py(yt_match.py)가 이걸로 곡마다
'유튜브에서 이 곡 듣기' 링크를 붙인다.

    python scripts/jukebox/fetch_yt_music.py

  assets/yt_videos.json  채널 6곳(public/data.js 에 있는 영상)의 길이·제목·설명란 시간표(챕터)
                         → 곡 하나짜리 영상, 또는 앨범 전체 영상의 '그 곡 시작 지점'(&t=초)
  assets/yt_music.json   아티스트 Topic 채널(유튜브 뮤직 음원 488곡) — 주크박스와는 대부분 다른 곡이라 보조용

YouTube Data API 키(YOUTUBE_API_KEY)가 필요하다 — 데스크탑 vault.env 에서 읽는다.
키가 없는 기계(미니PC 등)에서는 아무것도 하지 않고 성공으로 끝난다(지난 목록을 그대로 쓴다).
할당량: 영상 50개당 1~2단위 — 전체 약 30단위.
키 값은 메모리에만 두고 출력하지 않는다. 오류 메시지에도 주소(키 포함)를 찍지 않는다.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSETS = HERE / "assets"
TOPIC_CHANNEL = "UCl_D2zwR6AfgTBAJ6jQq00Q"          # yojosuknam - Topic
UPLOADS = "UU" + TOPIC_CHANNEL[2:]
VAULT = Path(r"d:/YH/APP/nexis-lab-home/vault.env")
API = "https://www.googleapis.com/youtube/v3/"
# 설명란 시간표 한 줄: '0:00 불턱 (The Fire Pit)', '[03:08] - 테왁', '1:02:03 | 제목'
CHAPTER_RE = re.compile(r"^\s*[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\])]?\s*[-–—|.:]?\s*(.+?)\s*$", re.M)


def api_key() -> str | None:
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"].strip()
    if VAULT.exists():
        m = re.search(r"^\s*YOUTUBE_API_KEY\s*=(.*)$", VAULT.read_text(encoding="utf-8-sig"), re.M)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def call(endpoint: str, key: str, **params) -> dict:
    q = urllib.parse.urlencode({**params, "key": key})
    try:
        with urllib.request.urlopen(f"{API}{endpoint}?{q}", timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        reason = ""
        try:
            reason = json.loads(e.read().decode("utf-8"))["error"]["errors"][0]["reason"]
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"{endpoint} HTTP {e.code} {reason}") from None


def iso_ms(d: str) -> int:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return ((h * 60 + mi) * 60 + s) * 1000


def secs(ts: str) -> int:
    n = 0
    for p in ts.split(":"):
        n = n * 60 + int(p)
    return n


def chapters(desc: str) -> list[list]:
    out = [[secs(t), title] for t, title in CHAPTER_RE.findall(desc or "")]
    # 시간표는 0:00 부터 늘어나는 순서여야 진짜다(본문 속 '3:16' 같은 숫자 배제)
    if len(out) < 2 or out[0][0] != 0 or any(b[0] <= a[0] for a, b in zip(out, out[1:])):
        return []
    return out


def details(key: str, ids: list[str], part: str) -> dict[str, dict]:
    got = {}
    for i in range(0, len(ids), 50):
        for v in call("videos", key, part=part, id=",".join(ids[i:i + 50])).get("items", []):
            got[v["id"]] = v
    return got


def channel_videos(key: str) -> list[dict]:
    raw = (REPO / "public" / "data.js").read_text(encoding="utf-8")
    items = json.loads(base64.b64decode(re.search(r"'([A-Za-z0-9+/=]+)'", raw).group(1)).decode("utf-8"))
    ch = {}
    for it in items:
        m = re.search(r"v=([\w-]{11})", it.get("playlist_url", ""))
        if m and it.get("source") == "youtube-api":
            ch[m.group(1)] = it.get("genre", "")
    got = details(key, list(ch), "snippet,contentDetails")
    return [{"id": vid, "ch": ch[vid], "title": v["snippet"]["title"],
             "ms": iso_ms(v["contentDetails"]["duration"]), "chapters": chapters(v["snippet"]["description"])}
            for vid, v in got.items()]


def topic_tracks(key: str) -> list[dict]:
    items, token = [], None
    while True:
        params = {"part": "snippet", "playlistId": UPLOADS, "maxResults": 50}
        if token:
            params["pageToken"] = token
        d = call("playlistItems", key, **params)
        for it in d.get("items", []):
            sn = it["snippet"]
            vid = sn.get("resourceId", {}).get("videoId")
            if vid and sn.get("title") not in ("Private video", "Deleted video"):
                items.append({"id": vid, "title": sn["title"], "at": sn.get("publishedAt", "")})
        token = d.get("nextPageToken")
        if not token:
            break
    ms = {k: iso_ms(v["contentDetails"]["duration"]) for k, v in details(key, [x["id"] for x in items], "contentDetails").items()}
    for x in items:
        x["ms"] = ms.get(x["id"], 0)
    return sorted(items, key=lambda x: x["at"])


def save(name: str, rows: list[dict], minimum: int) -> None:
    if len(rows) < minimum:
        print(f"[경고] {name}: {len(rows)}개뿐 — 이상하므로 기존 파일을 유지합니다")
        return
    (ASSETS / name).write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {name} {len(rows)}개")


def main() -> int:
    key = api_key()
    if not key:
        print("(YOUTUBE_API_KEY 없음 — 유튜브 링크 재료 갱신 생략, 지난 목록 사용)")
        return 0
    vids = channel_videos(key)
    save("yt_videos.json", vids, 100)
    print(f"    앨범 전체 영상(시간표 있음) {sum(1 for v in vids if v['chapters'])}개")
    save("yt_music.json", topic_tracks(key), 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
