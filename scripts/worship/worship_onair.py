#!/usr/bin/env python3
"""매일 온라인 예배 송출 — 미니PC 크론이 회차마다 실행(방송 예약 + 재인코딩 없는 송출 + 다시보기 정리).

    worship_onair.py ko|en                     # 크론: 예배 5분 전(대기 화면 5분이 영상 앞에 들어 있음)
    worship_onair.py ko --dry --at '2026-11-06 09:55'   # 제목·설명·판단만 출력(유튜브 접속 없음)
    worship_onair.py ko --test 60              # 비공개 시험 방송(지금 있는 READY 영상의 앞 60초)

시간표(KST): 한국어 10·16·22·04시 / 영어 13·19·01·07시. D일 영상은 D일 10시부터 다음 날 07시 회차까지 쓴다.
영상: D일 READY → 없으면 D-1일 READY('재방송' 표시·알림) → 둘 다 없으면 건너뛰고 알림.
다시보기: 10시 한국어·13시 영어만 공개로 남겨 재생목록에 넣고, 나머지 회차·재방송은 끝나면 비공개로 돌린다.
비밀값: 토큰은 파일에서만 읽고 스트림 주소는 로그·화면에 남기지 않는다(worship_ops.clean 이 가린다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worship_ops as ops  # noqa: E402

B = Path(os.environ.get("WORSHIP_BASE", "/mnt/external/nexis-worship"))
TOKEN = B / ".youtube_token_live.pickle"
KST = dt.timezone(dt.timedelta(hours=9))
FIRST_ON_AIR = dt.datetime(2026, 11, 6, 9, 30, tzinfo=KST)  # 첫 방송 11-06 10시 — 그 전 회차는 돌지 않는다
KEEP_HOUR = {"ko": 10, "en": 13}                            # 이 회차의 다시보기를 그날의 영상으로 남긴다
PLAYLIST = {"ko": ("매일 온라인 예배", "매일 새로 드리는 한국어 온라인 예배 모음입니다."),
            "en": ("Daily Online Worship", "A new online worship service every day.")}
QT_LINK = "https://malsseum.yojosuknam.com/?src=youtube"
CHAPTER = re.compile(r"^\d{1,2}:\d{2}(:\d{2})? ")
AMPM_KO = lambda h: "새벽" if h < 6 else "오전" if h < 12 else "오후" if h < 18 else "저녁" if h < 21 else "밤"


def service_time(now: dt.datetime) -> dt.datetime:
    """크론은 정각 5분 전에 돈다 → 예배가 시작되는 정각"""
    base = now.replace(minute=0, second=0, microsecond=0)
    return base + dt.timedelta(hours=1) if now.minute >= 30 else base


def service_date(service: dt.datetime) -> dt.date:
    """01·04·07시 회차는 전날 영상(새 영상은 10시부터)"""
    return service.date() if service.hour >= 10 else service.date() - dt.timedelta(days=1)


def folder(day: dt.date, lang: str) -> Path:
    return B / "output" / f"{day}_{lang}"


def pick_video(day: dt.date, lang: str) -> tuple[Path | None, bool]:
    """(폴더, 재방송 여부)"""
    for d, rerun in ((day, False), (day - dt.timedelta(days=1), True)):
        o = folder(d, lang)
        if (o / "READY").exists() and (o / f"worship_{d}_{lang}.mp4").exists():
            return o, rerun
    return None, False


def hour_ko(h: int) -> str:
    return f"{AMPM_KO(h)} {h % 12 or 12}시"


def tidy(title: str) -> str:
    return re.sub(r"\bGods\b", "God's", title)


def build_text(o: Path, lang: str, service: dt.datetime, rerun: bool, test: bool) -> tuple[str, str]:
    s = json.loads((o / "script.json").read_text(encoding="utf-8"))
    old = json.loads((o / "spec.json").read_text(encoding="utf-8"))["description"].splitlines()
    chapters = [tidy(l) for l in old if CHAPTER.match(l)]
    credits = [l for l in old if l.startswith("🎵")]
    mins = round((s.get("total_sec") or 0) / 60)
    head = tidy(s["title"])
    verses = s.get("verses") or []
    quote = "\n".join(f"“{v['text']}” ({v['reference']})" for v in verses[:2])
    prefix = "[시험] " if test else ""
    if lang == "ko":
        tag = "재방송 · " if rerun else ""
        title = f"{prefix}[매일 온라인 예배] {head} · {s['passage']} | {tag}{service.month}/{service.day} {hour_ko(service.hour)}"
        intro = f"{hour_ko(service.hour)} 정각에 예배를 시작합니다. 앞 5분은 조용히 마음을 준비하는 시간이고, 이어서 약 {mins}분 동안 찬송과 기도, 말씀, 기도회로 함께합니다.\n혼자 계신 자리에서도, 바쁜 하루 가운데서도 편하게 함께해 주세요."
        if rerun:
            intro = "오늘 예배 준비가 늦어져 지난 예배를 다시 드립니다. 새 예배는 준비되는 대로 다음 회차부터 방송합니다.\n\n" + intro
        lines = [f"{head} — {s['passage']}", "", intro, "", f"📖 오늘의 말씀 · {s['passage']}", quote, "",
                 "🕊 예배 순서", *chapters, "",
                 "⏰ 매일 방송 시간(한국 시간)", "한국어  오전 10시 · 오후 4시 · 밤 10시 · 새벽 4시", "English  오후 1시 · 저녁 7시 · 새벽 1시 · 오전 7시", "",
                 "🙏 함께 알아 두세요",
                 "미리 제작한 예배를 시간표에 맞춰 내보내는 방송입니다. 설교와 기도는 AI의 도움으로 준비했고, 낭독은 운영자의 목소리를 AI로 합성했습니다.",
                 "교회 공동체와 목회 상담을 대신하지 않습니다. 가까운 교회와 함께해 주세요. 어려움이 있으시면 주변의 믿을 만한 분이나 전문가에게 꼭 도움을 청해 주세요.",
                 "성경: 개역한글(저작권 만료)", *credits, "",
                 f"📱 오늘 말씀을 더 깊이 묵상하기 → 말씀Log {QT_LINK}", "",
                 "#온라인예배 #매일예배 #말씀묵상 #찬송 #기도"]
    else:
        ny = service.astimezone(ZoneInfo("America/New_York"))
        la = service.astimezone(ZoneInfo("America/Los_Angeles"))
        fmt = lambda t: f"{t.hour % 12 or 12} {'AM' if t.hour < 12 else 'PM'}"
        when = f"{service.strftime('%b')} {service.day}, {fmt(service)} KST"
        tag = "Rebroadcast · " if rerun else ""
        title = f"{prefix}[Daily Online Worship] {head} · {s['passage']} | {tag}{when}"
        intro = (f"The service begins at {fmt(service)} Korea time ({fmt(ny)} New York / {fmt(la)} Los Angeles). The first 5 minutes are a quiet time to prepare your heart, "
                 f"followed by about {mins} minutes of hymns, prayer, the Word and a time of prayer together.\nWherever you are and however busy your day, you are welcome here.")
        if rerun:
            intro = "Today's service is still being prepared, so we are sharing the previous service again. A new service will air as soon as it is ready.\n\n" + intro
        lines = [f"{head} — {s['passage']}", "", intro, "", f"📖 Today's Scripture · {s['passage']}", quote, "",
                 "🕊 Order of Worship", *chapters, "",
                 "⏰ Daily schedule (Korea time)", "English  1 PM · 7 PM · 1 AM · 7 AM", "한국어  10 AM · 4 PM · 10 PM · 4 AM", "",
                 "🙏 Please note",
                 "This is a pre-produced service broadcast on schedule. The sermon and prayers were prepared with the help of AI, and the reading voice is an AI synthesis of the host's own voice.",
                 "It does not replace a church community or pastoral care. Please stay connected with a local church, and if you are struggling, reach out to someone you trust or a professional.",
                 "Scripture: King James Version (public domain)", *credits, "",
                 f"📱 Go deeper with Malsseum Log {QT_LINK}", "",
                 "#OnlineWorship #DailyWorship #Devotion #Hymns #Prayer"]
    return title[:100], "\n".join(lines)[:4900]


def youtube():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    c = pickle.loads(TOKEN.read_bytes())
    if not c.valid:
        c.refresh(Request())
        TOKEN.write_bytes(pickle.dumps(c))
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def get_stream(y, lang: str) -> dict:
    name = f"nexis-online-worship-{lang}"
    for s in y.liveStreams().list(part="id,snippet,cdn", mine=True, maxResults=50).execute().get("items", []):
        if s["snippet"]["title"] == name:
            return s
    return y.liveStreams().insert(part="snippet,cdn,contentDetails", body={
        "snippet": {"title": name},
        "cdn": {"ingestionType": "rtmp", "resolution": "1080p", "frameRate": "30fps"},
        "contentDetails": {"isReusable": True}}).execute()


def get_playlist(y, lang: str) -> str:
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


def lifecycle(y, bid: str) -> str:
    items = y.liveBroadcasts().list(part="status", id=bid).execute().get("items", [])
    return items[0]["status"]["lifeCycleStatus"] if items else "없음"


def send(y, bid: str, mp4: Path, url: str, limit: int | None) -> tuple[bool, str]:
    """ffmpeg 그대로 복사 송출. (성공 여부, 사유). 끝날 때까지 기다린다."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-re", "-i", str(mp4)]
    if limit:
        cmd += ["-t", str(limit)]
    cmd += ["-c", "copy", "-f", "flv", url]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace")
    live, t0, state = False, time.time(), ""
    while p.poll() is None:
        time.sleep(30)
        if not live:   # 방송이 켜지는 걸 볼 때까지만 조회(할당량 절약)
            try:
                state = lifecycle(y, bid)
                live = state == "live"
            except Exception as e:  # 조회 실패로 송출을 끊지 않는다
                state = type(e).__name__
    err = ops.clean((p.stderr.read() or "").strip()[-300:])
    if p.returncode != 0:
        return False, f"송출 오류 {time.time() - t0:.0f}초 만에: {err or p.returncode}"
    if not live:  # 보내긴 했는데 유튜브에서 방송이 켜진 걸 한 번도 못 봤다
        try:
            state = lifecycle(y, bid)
        except Exception as e:
            state = type(e).__name__
        if state not in ("live", "complete"):
            return False, f"영상은 보냈지만 방송이 켜지지 않았어요(상태 {state})"
    return True, ""


def finish(y, bid: str, keep: bool, lang: str, private_only: bool) -> str:
    """방송 종료를 기다려 다시보기 정리 — 보관본은 공개·재생목록, 나머지는 비공개"""
    for _ in range(40):
        try:
            if lifecycle(y, bid) == "complete":
                break
        except Exception:
            pass
        time.sleep(30)
    else:
        try:
            y.liveBroadcasts().transition(part="status", id=bid, broadcastStatus="complete").execute()
        except Exception as e:
            return f"방송 종료 확인 실패({type(e).__name__})"
    pv = "public" if keep and not private_only else "private"
    last = ""
    for _ in range(10):  # 다시보기 처리 직후엔 수정이 거절될 수 있다
        try:
            it = y.videos().list(part="status", id=bid).execute()["items"][0]["status"]
            st = {k: it[k] for k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids") if k in it}
            st.update(privacyStatus=pv, containsSyntheticMedia=True)
            y.videos().update(part="status", body={"id": bid, "status": st}).execute()
            if pv == "public":
                y.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": get_playlist(y, lang), "resourceId": {"kind": "youtube#video", "videoId": bid}}}).execute()
            return "다시보기 공개·재생목록" if pv == "public" else "다시보기 비공개"
        except Exception as e:
            last = type(e).__name__
            time.sleep(60)
    return f"다시보기 정리 실패({last})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lang", choices=["ko", "en"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--at", help="시험용 현재 시각 'YYYY-MM-DD HH:MM'(KST)")
    ap.add_argument("--test", type=int, help="비공개 시험 방송 길이(초)")
    a = ap.parse_args()
    now = dt.datetime.strptime(a.at, "%Y-%m-%d %H:%M").replace(tzinfo=KST) if a.at else dt.datetime.now(KST)
    lang = a.lang
    if not a.test and not a.dry and now < FIRST_ON_AIR:
        return 0
    service = service_time(now)
    day = service_date(service)
    slot = service.strftime("%Y-%m-%d %H:%M")
    o, rerun = pick_video(day, lang)
    name = "한국어" if lang == "ko" else "영어"

    def ev(status, detail, **extra):
        rec = {"ts": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), "date": str(day), "lang": lang, "stage": "onair",
               "status": status, "detail": ops.clean(detail), "slot": slot, "test": bool(a.test), **extra}
        if a.dry:
            return
        ops.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (ops.LOG_DIR / "schedule.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if not o:
        ev("fail", "방송할 영상 없음(오늘·어제 모두 READY 없음)")
        if not a.dry and not a.test:
            ops.notify(f"🚨 {slot} {name} 예배 회차를 건너뜁니다 — 오늘·어제 영상 모두 완성본이 없습니다.")
        print("방송할 영상 없음")
        return 1
    title, desc = build_text(o, lang, service, rerun, bool(a.test))
    keep = service.hour == KEEP_HOUR[lang] and not rerun and not a.test
    mp4 = o / f"worship_{o.name}.mp4"
    if a.dry:
        print(f"회차 {slot} | 영상 {mp4.name} | 재방송 {rerun} | 다시보기 {'공개 보관' if keep else '비공개'}")
        print("제목:", title, f"({len(title)}자)")
        print(desc)
        return 0

    bid = ""
    try:
        y = youtube()
        st = get_stream(y, lang)
        start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=30)).isoformat()
        bc = y.liveBroadcasts().insert(part="snippet,status,contentDetails", body={
            "snippet": {"title": title, "description": desc, "scheduledStartTime": start},
            "status": {"privacyStatus": "private" if a.test else "public", "selfDeclaredMadeForKids": False},
            "contentDetails": {"enableAutoStart": True, "enableAutoStop": True, "enableDvr": True, "recordFromStart": True,
                               "enableEmbed": True, "latencyPreference": "normal", "monitorStream": {"enableMonitorStream": False}}}).execute()
        bid = bc["id"]
        y.liveBroadcasts().bind(part="id,contentDetails", id=bid, streamId=st["id"]).execute()
        ing = st["cdn"]["ingestionInfo"]
        url = f"{ing['ingestionAddress']}/{ing['streamName']}"
        link = f"https://youtu.be/{bid}"
        ev("start", "방송 시작", title=title, url=link, keep=keep, rerun=rerun)
        if rerun and not a.test:
            ops.notify(f"⚠️ {slot} {name} 예배: 오늘 영상이 없어 지난 영상을 재방송합니다. {link}")
        t0 = time.time()
        ok, why = send(y, bid, mp4, url, a.test)
        if not ok and time.time() - t0 < 180:  # 시작하자마자 끊겼으면 한 번 더
            time.sleep(20)
            ok, why = send(y, bid, mp4, url, a.test)
        result = finish(y, bid, keep, lang, bool(a.test))
        if not ok:
            ev("fail", why, title=title, url=link)
            ops.notify(f"🚨 예배 시험 방송 실패 — 첫 방송 전에 확인 필요: {why}" if a.test else f"🚨 {slot} {name} 예배 송출 실패: {why}\n{link}")
            return 1
        ev("ok", result, title=title, url=link, keep=keep, rerun=rerun)
        if "실패" in result and not a.test:
            ops.notify(f"⚠️ {slot} {name} 예배: 방송은 끝났지만 {result}. {link}")
        if a.test:
            ops.notify(f"✅ 예배 시험 방송 성공({name} {a.test}초, 비공개): {result}. 첫 방송 준비 완료. {link}")
        print("끝", link, result)
        return 0
    except Exception as e:
        why = f"{type(e).__name__}: {ops.clean(str(e), 160)}"
        ev("fail", why, url=f"https://youtu.be/{bid}" if bid else "")
        ops.notify(("🚨 예배 시험 방송 실패 — 첫 방송 전에 확인 필요: " if a.test else f"🚨 {slot} {name} 예배 방송을 시작하지 못했습니다: ") + why)
        print("실패", why)
        return 1


if __name__ == "__main__":
    sys.exit(main())
