"""
1분 묵상(nexis-qt) 채널 실시간 예배 — 방송 예약 · 상태 확인. autovid-bot 컨테이너 안에서 돈다(채널 토큰이 거기 있다).

    python worship_live.py schedule /tmp/worship_<date>_<lang>.json   # 방송 예약 + 스트림 연결 + 재생목록
    python worship_live.py status <broadcastId>

라이브가 끝나면 유튜브가 같은 주소의 일반 영상으로 저장한다(따로 올리지 않는다, 업로드 할당량 0).
그래서 제목·설명(순서별 챕터)·재생목록을 예약할 때 미리 넣어 둔다 → 끝나는 순간 다시보기 영상이 갖춰져 있다.
스트림 키는 /tmp/worship_streamkey_<lang> 로만 내보내고(호스트가 600 파일로 옮긴 뒤 지운다) 화면·로그에 찍지 않는다.
할당량(하루 1만, autovid·라디오와 공유): 방송 1개 ≈ insert 50 + bind 50 + 재생목록 50 = 150.
"""
from __future__ import annotations

import json
import pickle
import sys

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN = "/app/.youtube_token_nexis-qt.pickle"
STREAM_TITLE = "nexis-worship-{lang}"   # 언어별 따로 — 한 스트림에 방송 두 개를 묶으면 어느 쪽이 켜질지 꼬인다
PLAYLIST = {"ko": ("말씀 묵상 예배", "매일 아침 6시, 말씀Log 본문으로 드리는 20분 실시간 예배"),
            "en": ("Worship in the Word", "A 20-minute live worship service every day, from the Malsseum Log devotion")}


def yt():
    c = pickle.load(open(TOKEN, "rb"))
    if not c.valid and c.refresh_token:
        c.refresh(Request())
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def stream(y, lang: str) -> dict:
    """예배용 스트림(키 고정) — 없으면 만든다."""
    for s in y.liveStreams().list(part="id,snippet,cdn", mine=True, maxResults=50).execute().get("items", []):
        if s["snippet"]["title"] == STREAM_TITLE.format(lang=lang):
            return s
    return y.liveStreams().insert(part="snippet,cdn,contentDetails", body={
        "snippet": {"title": STREAM_TITLE.format(lang=lang)},
        "cdn": {"ingestionType": "rtmp", "resolution": "1080p", "frameRate": "30fps"},
        "contentDetails": {"isReusable": True}}).execute()


def playlist(y, lang: str) -> str:
    title, desc = PLAYLIST[lang]
    req = y.playlists().list(part="id,snippet", mine=True, maxResults=50)
    while req:
        r = req.execute()
        for p in r.get("items", []):
            if p["snippet"]["title"] == title:
                return p["id"]
        req = y.playlists().list_next(req, r)
    return y.playlists().insert(part="snippet,status", body={
        "snippet": {"title": title, "description": desc, "defaultLanguage": lang},
        "status": {"privacyStatus": "public"}}).execute()["id"]


def schedule(spec_path: str) -> None:
    """spec = {lang, start (RFC3339), title, description, privacy}"""
    spec = json.load(open(spec_path, encoding="utf-8"))
    y = yt()
    st = stream(y, spec["lang"])
    bc = y.liveBroadcasts().insert(part="snippet,status,contentDetails", body={
        "snippet": {"title": spec["title"][:100], "description": spec["description"][:4900],
                    "scheduledStartTime": spec["start"]},
        "status": {"privacyStatus": spec.get("privacy", "public"), "selfDeclaredMadeForKids": False},
        "contentDetails": {"enableAutoStart": True, "enableAutoStop": True, "enableDvr": True,
                           "recordFromStart": True, "enableEmbed": True, "latencyPreference": "normal",
                           "monitorStream": {"enableMonitorStream": False}}}).execute()
    y.liveBroadcasts().bind(part="id,contentDetails", id=bc["id"], streamId=st["id"]).execute()
    y.playlistItems().insert(part="snippet", body={"snippet": {
        "playlistId": playlist(y, spec["lang"]), "resourceId": {"kind": "youtube#video", "videoId": bc["id"]}}}).execute()
    ing = st["cdn"]["ingestionInfo"]
    with open(f"/tmp/worship_streamkey_{spec['lang']}", "w") as f:
        f.write(f"{ing['ingestionAddress']}/{ing['streamName']}")
    print(json.dumps({"broadcast": bc["id"], "url": f"https://youtu.be/{bc['id']}", "start": spec["start"]}))


def status(bid: str) -> None:
    r = yt().liveBroadcasts().list(part="id,status", id=bid).execute().get("items", [])
    print(r[0]["status"]["lifeCycleStatus"] if r else "없음")


if __name__ == "__main__":
    {"schedule": schedule, "status": status}[sys.argv[1]](sys.argv[2])
