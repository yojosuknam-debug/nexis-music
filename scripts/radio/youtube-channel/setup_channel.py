"""
yojosuknam Radio 유튜브 채널 꾸미기 + 24시간 라이브 방송 만들기 (한 번 실행).
autovid-bot 컨테이너 안에서 nexis-horror 토큰(scope youtube)으로 돈다.

    docker exec -i autovid-bot python /tmp/setup_channel.py

- 채널 소개글·키워드·배너
- liveStream(재사용, rtmp) + liveBroadcast(공개, 자동 시작, 음악) 연결, 썸네일
- 스트림 키는 /tmp/ytkey (600) 에만 쓴다 — 화면에 찍지 않는다. 호출한 쪽이 radio.env 로 옮기고 지운다.
이미 만든 방송·스트림이 있으면 새로 만들지 않고 재사용한다.
--live-only : 채널 꾸미기(배너 업로드 등 할당량 큰 호출)를 건너뛴다 — 자동 재시도(youtube-go.sh)용.
  유튜브 API 하루 할당량을 autovid 업로드와 같이 쓰므로 재시도에서 아낀다.
"""
import os
import pickle
import sys

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN = "/app/.youtube_token_nexis-horror.pickle"
BANNER = "/tmp/banner-2560x1440.jpg"
THUMB = "/tmp/thumb-1280x720.jpg"
STREAM_TITLE = "yojosuknam Radio main"

DESC = """🐻📻 yojosuknam Radio — 24시간 음악 방송

yojosuknam 의 앨범을 시간대별 편성에 따라 골라 처음부터 끝까지, 하루 종일 이어서 틉니다.
낮(07–22시)은 채널별 정규 방송이 하루 3번 돌고, 밤(22–07시)은 로파이 위주 심야 방송이에요.
Lo-fi · 재즈합 · 국악 퓨전 · K-팝 · CCM · 감성 발라드 — 광고·멘트 없이 음악만.

yojosuknam Radio plays original albums by yojosuknam around the clock —
lo-fi, jazz hop, Korean gugak fusion, K-pop, CCM and ballads. No ads, no talk, just music.

▶ 방송 페이지 (곡별 유튜브 링크·가사): https://music.yojosuknam.com/radio
📻 라디오 앱·VLC 로 듣기: https://stream.yojosuknam.com/live.mp3
🎵 앨범 전체: https://music.yojosuknam.com/album
🎤 아티스트 yojosuknam 정식 음원 (유튜브 뮤직): https://www.youtube.com/channel/UCl_D2zwR6AfgTBAJ6jQq00Q
✉ 문의: support@nexis-lab.com"""

KEYWORDS = ('yojosuknam "yojosuknam Radio" "24/7 radio" lofi "jazz hop" gugak "korean music" kpop ccm '
            '"study music" "relaxing music" 라디오 로파이 국악 재즈 음악방송')

try:     # 편성표(youtube-chat.sh 가 schedule.py/json 을 /tmp 에 같이 넣는다)
    sys.path.insert(0, "/tmp")
    import schedule
    TIMETABLE = "\n\n" + schedule.timetable_text()
except Exception:  # noqa: BLE001
    TIMETABLE = ""

LIVE_TITLE = "yojosuknam Radio 📻 24/7 Lo-fi · Jazz Hop · 국악 퓨전 · K-Pop · CCM | 쉬지 않는 음악 방송"
LIVE_DESC = """▶ 지금 곡 원곡 영상 바로가기: https://music.yojosuknam.com/radio
📱 화면 오른쪽 아래 QR 을 폰으로 찍으면 지금 나오는 곡의 원곡 영상이 열려요.

""" + DESC + """

지금 나오는 곡과 다음 곡은 화면에, 곡별 원곡 영상 링크는 방송 페이지와 화면 QR 에 있어요.
화면 색과 배지는 그 곡이 원래 올라간 채널(Midnight Radio · Hanguk Sounds · Miso Beats · Still Waters · 쉬어가는 감성 음악 · 굳이 송)을 뜻합니다.""" + TIMETABLE + """

#yojosuknam #lofi #24시간라디오"""


def main() -> None:
    c = pickle.load(open(TOKEN, "rb"))
    if not c.valid:
        c.refresh(Request())
    y = build("youtube", "v3", credentials=c, cache_discovery=False)

    # 1) 채널 소개·키워드·배너 (brandingSettings 는 통째로 다시 보내야 다른 값이 안 지워진다)
    if "--live-only" in sys.argv:
        print("채널 꾸미기 건너뜀(--live-only)")
    else:
        brand(y)
    live(y)


def brand(y) -> None:
    ch = y.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    bs = ch["brandingSettings"]
    bs.setdefault("channel", {})
    bs["channel"].update({"description": DESC, "keywords": KEYWORDS, "defaultLanguage": "ko", "country": "KR"})
    if os.path.exists(BANNER):
        up = y.channelBanners().insert(media_body=MediaFileUpload(BANNER, mimetype="image/jpeg")).execute()
        bs.setdefault("image", {})["bannerExternalUrl"] = up["url"]
    bs.pop("hints", None)
    y.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": bs}).execute()
    print("채널 소개글·키워드·배너 적용")


def live(y) -> None:
    # 2) 스트림(재사용)
    streams = y.liveStreams().list(part="id,snippet,cdn", mine=True, maxResults=50).execute().get("items", [])
    st = next((s for s in streams if s["snippet"]["title"] == STREAM_TITLE), None)
    if not st:
        st = y.liveStreams().insert(part="snippet,cdn,contentDetails", body={
            "snippet": {"title": STREAM_TITLE},
            "cdn": {"ingestionType": "rtmp", "resolution": "variable", "frameRate": "variable"},
            "contentDetails": {"isReusable": True}}).execute()
        print("라이브 스트림 생성")
    else:
        print("라이브 스트림 재사용")

    # 3) 방송(자동 시작·자동 종료 없음)
    bcs = y.liveBroadcasts().list(part="id,snippet,status,contentDetails",  # broadcastStatus 는 mine 과 함께 못 씀(내 방송만 반환)
                                  broadcastStatus="upcoming", maxResults=50).execute().get("items", [])
    bcs += y.liveBroadcasts().list(part="id,snippet,status,contentDetails",
                                   broadcastStatus="active", maxResults=50).execute().get("items", [])
    bc = next((b for b in bcs if b["snippet"]["title"].startswith("yojosuknam Radio")), None)
    if not bc:
        import datetime
        start = (datetime.datetime.utcnow() + datetime.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        bc = y.liveBroadcasts().insert(part="snippet,status,contentDetails", body={
            "snippet": {"title": LIVE_TITLE, "description": LIVE_DESC, "scheduledStartTime": start},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            "contentDetails": {"enableAutoStart": True, "enableAutoStop": False, "enableDvr": True,
                               "latencyPreference": "normal", "recordFromStart": True}}).execute()
        print("라이브 방송 생성")
    else:
        print("라이브 방송 재사용")
    y.liveBroadcasts().bind(part="id,contentDetails", id=bc["id"], streamId=st["id"]).execute()

    # 음악 카테고리(10)·썸네일
    y.videos().update(part="snippet", body={"id": bc["id"], "snippet": {
        "title": LIVE_TITLE, "description": LIVE_DESC, "categoryId": "10",
        "tags": ["yojosuknam", "yojosuknam Radio", "lofi", "jazz hop", "gugak", "24/7 radio", "라디오"],
        "defaultLanguage": "ko", "defaultAudioLanguage": "ko"}}).execute()
    if os.path.exists(THUMB):
        y.thumbnails().set(videoId=bc["id"], media_body=MediaFileUpload(THUMB, mimetype="image/jpeg")).execute()
    print("방송 주소: https://www.youtube.com/watch?v=" + bc["id"])

    # 4) 스트림 키 — 파일에만
    key = st["cdn"]["ingestionInfo"]["streamName"]
    fd = os.open("/tmp/ytkey", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key)
    print("스트림 키 → /tmp/ytkey (출력 안 함)")


if __name__ == "__main__":
    main()
