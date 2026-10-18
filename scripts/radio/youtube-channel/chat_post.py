"""
yojosuknam Radio 유튜브 라이브 채팅 (youtube-chat.sh 가 부른다).
autovid-bot 컨테이너 안에서 nexis-horror 토큰(scope youtube)으로 돈다 — setup_channel.py 와 같은 방식.
    docker exec autovid-bot python /tmp/chat_post.py --program # 편성이 바뀌었을 때: 지금 장르·채널 주소 (schedule.py/json 도 /tmp 에)
    docker exec autovid-bot python /tmp/chat_post.py           # 지금 곡 원곡 링크 1건(수동용)
    docker exec autovid-bot python /tmp/chat_post.py --desc    # 설명란만 다시 적용(setup_channel.py 도 /tmp 에 있어야 함)
할당량(하루 10,000, autovid 와 공유): 방송 조회 1 + 채팅 50 = 1회 51단위 → 편성 전환 하루 약 23회 ≈ 1,200단위.
진행 중인 방송이 없으면 '방송 없음'을 출력하고 끝낸다(감시 겸용 — 로그에서 확인).
"""
import json
import pickle
import re
import sys
import urllib.request

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN = "/app/.youtube_token_nexis-horror.pickle"
NOW_URL = "https://audio.yojosuknam.com/radio/nowplaying.json"
RADIO_PAGE = "https://music.yojosuknam.com/radio"


def clean(text: str) -> str:
    keep = (ch for ch in text if not (ord(ch) >= 0x1F000 or 0x2600 <= ord(ch) <= 0x27BF
                                       or 0x2B00 <= ord(ch) <= 0x2BFF or ch in "️‍"))
    return " ".join("".join(keep).split())


def short_yt(url: str) -> str:
    m = re.search(r"[?&]v=([\w-]{11})", url or "")
    if not m:
        return ""
    t = re.search(r"[?&]t=(\d+)", url)
    return f"https://youtu.be/{m.group(1)}" + (f"?t={t.group(1)}" if t and t.group(1) != "0" else "")


def message(now: dict) -> str:
    link = short_yt(now.get("youtube", ""))
    title = clean(now.get("title", ""))
    tail = f" ▶ 원곡 영상 {link} · 곡별 링크 모음 {RADIO_PAGE}" if link else f" ▶ 곡별 원곡 링크 모음 {RADIO_PAGE}"
    room = 200 - len("🎧 지금 흐르는 곡: ") - len(tail)          # 유튜브 채팅 한 건 최대 200자
    if len(title) > room:
        title = title[:room - 1] + "…"
    return f"🎧 지금 흐르는 곡: {title}{tail}"


def program_message(now: dict) -> str:
    sys.path.insert(0, "/tmp")
    import schedule
    st = now.get("station", "")
    cur, nxt = schedule.program(int(now.get("at") or 0) / 1000, st)
    i, n = schedule.info(st), schedule.info(nxt["station"])
    part = "정규 방송" if cur["regular"] else "심야 방송"
    text = (f"📻 {part} 편성 전환 — 지금은 {i.get('icon', '')} {st} · {i.get('genre', '')}"
            f" ({schedule.hhmm(cur['start'])}~{schedule.hhmm(cur['end'])})")
    if i.get("url"):
        text += f" ▶ 채널 {i['url']}"
    text += f" · 다음 {schedule.hhmm(nxt['start'])} {n.get('icon', '')} {nxt['station']} · 편성표 {RADIO_PAGE}"
    return text[:200]


def main() -> None:
    c = pickle.load(open(TOKEN, "rb"))
    if not c.valid:
        c.refresh(Request())
    y = build("youtube", "v3", credentials=c, cache_discovery=False)
    bcs = y.liveBroadcasts().list(part="id,snippet", broadcastStatus="active",
                                  maxResults=10).execute().get("items", [])
    bc = next((b for b in bcs if b["snippet"]["title"].startswith("yojosuknam Radio")), None)
    if not bc:
        print("방송 없음 — 라이브가 꺼져 있다(확인 필요)")
        return

    if "--desc" in sys.argv:
        sys.path.insert(0, "/tmp")
        from setup_channel import LIVE_DESC, LIVE_TITLE
        y.videos().update(part="snippet", body={"id": bc["id"], "snippet": {
            "title": LIVE_TITLE, "description": LIVE_DESC, "categoryId": "10",
            "tags": ["yojosuknam", "yojosuknam Radio", "lofi", "jazz hop", "gugak", "24/7 radio", "라디오"],
            "defaultLanguage": "ko", "defaultAudioLanguage": "ko"}}).execute()
        print("설명란 적용")
        return

    req = urllib.request.Request(NOW_URL, headers={"User-Agent": "NexisRadio/1.0"})
    now = json.load(urllib.request.urlopen(req, timeout=15)).get("now") or {}
    text = program_message(now) if "--program" in sys.argv else message(now)
    y.liveChatMessages().insert(part="snippet", body={"snippet": {
        "liveChatId": bc["snippet"]["liveChatId"], "type": "textMessageEvent",
        "textMessageDetails": {"messageText": text}}}).execute()
    print("채팅 올림:", text)


if __name__ == "__main__":
    main()
