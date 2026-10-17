"""
yojosuknam Radio → 유튜브 24시간 라이브.

    (미니PC) docker compose --profile youtube up -d

소리 = 같은 미니PC Icecast 의 MP3 직통(http://icecast:8000/live.mp3) — 방송과 똑같은 소리.
화면 = 지금 곡의 앨범 커버·제목·앨범·다음 곡·방송 주소를 1280×720 한 장으로 그려
       곡이 바뀔 때마다 갈아 끼운다(ffmpeg image2 는 매 프레임 파일을 다시 읽는다).

환경변수(~/.config/nexis/radio.env):
    YOUTUBE_STREAM_KEY   유튜브 스튜디오 → 라이브 → 스트림 키 (없으면 시작하지 않는다)
    YOUTUBE_RTMP         기본 rtmp://a.rtmp.youtube.com/live2
스트림 키는 비밀값 — 로그에 찍히지 않게 ffmpeg 출력에서 가린다.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

KEY = os.environ.get("YOUTUBE_STREAM_KEY", "").strip()
RTMP = os.environ.get("YOUTUBE_RTMP", "rtmp://a.rtmp.youtube.com/live2").rstrip("/")
AUDIO = os.environ.get("RADIO_AUDIO_URL", "http://icecast:8000/live.mp3")
NOW_URL = os.environ.get("RADIO_NOW_URL", "https://audio.yojosuknam.com/radio/nowplaying.json")
W, H, FPS = 1280, 720, 10
OUT = Path("/tmp/yt")
FRAME = OUT / "frame.jpg"
UA = "Mozilla/5.0 (X11; Linux x86_64) NexisRadio/1.0"
FONT_B = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
FONT_R = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
# 곡이 원래 올라간 유튜브 채널별 화면 색·소개 (scripts/jukebox/yt_match.py STATIONS 와 이름이 같아야 함)
THEMES = {
    "Midnight Radio":     ((112, 132, 255), "Midnight Radio", "Lo-fi · Jazz Hop · 깊은 밤의 라디오"),
    "Hanguk Sounds":      ((70, 190, 150), "Hanguk Sounds", "국악 퓨전 · 가야금·해금·대금의 오늘"),
    "Miso Beats":         ((255, 150, 90), "Miso Beats", "K-어반 팝 · R&B · 비트"),
    "Still Waters":       ((140, 196, 255), "Still Waters", "Christian Lofi · CCM · 쉼과 묵상"),
    "쉬어가는 감성 음악":  ((240, 146, 170), "쉬어가는 감성 음악", "감성 발라드 · 레트로 · 잠깐 쉬어가요"),
    "굳이 송":            ((255, 206, 70), "굳이 송", "코믹 송 · 굳이 이걸 노래로"),
}
DEFAULT_THEME = ((200, 206, 212), "yojosuknam Radio", "yojosuknam 의 앨범을 24시간")
AUDIO_LAG = 3.0          # Icecast 소리가 송출기 시각보다 늦게 오는 정도(초)
stop = threading.Event()


def log(msg: str) -> None:
    if KEY:
        msg = msg.replace(KEY, "***")
    print(time.strftime("%m-%d %H:%M:%S"), msg, flush=True)


def fetch(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


FALLBACK = {FONT_B: "C:/Windows/Fonts/malgunbd.ttf", FONT_R: "C:/Windows/Fonts/malgun.ttf"}   # 데스크탑 시험용


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    for p in (path, FALLBACK.get(path, "")):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(d: ImageDraw.ImageDraw, text: str, f, width: int, lines: int) -> list[str]:
    """띄어쓰기 단위로 줄을 나눈다(영어 단어가 중간에서 끊기지 않게).
    한 단어가 한 줄보다 길 때만 글자 단위로 자른다. 넘치면 마지막 줄 끝을 … 로."""
    fits = lambda s: d.textlength(s, font=f) <= width
    out, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if fits(cand):
            cur = cand
            continue
        if cur:
            out.append(cur)
            cur = ""
        while not fits(word):                      # 너무 긴 한 단어
            i = len(word)
            while i > 1 and not fits(word[:i]):
                i -= 1
            out.append(word[:i])
            word = word[i:]
        cur = word
    if cur:
        out.append(cur)
    if len(out) > lines:
        last = out[lines - 1]
        while last and not fits(last + "…"):
            last = last[:-1]
        out = out[:lines - 1] + [last.rstrip() + "…"]
    return out or [""]


_cover_cache: dict[str, Image.Image] = {}


def cover(url: str) -> Image.Image:
    if url not in _cover_cache:
        try:
            _cover_cache.clear()
            _cover_cache[url] = Image.open(io.BytesIO(fetch(url))).convert("RGB")
        except Exception:  # noqa: BLE001
            _cover_cache[url] = Image.new("RGB", (800, 800), (40, 46, 58))
    return _cover_cache[url]


def render(now: dict, nxt: dict | None) -> None:
    c = cover(now.get("cover", ""))
    bg = c.resize((W, W)).crop((0, (W - H) // 2, W, (W + H) // 2)).filter(ImageFilter.GaussianBlur(40))
    color, label, tagline = THEMES.get(now.get("station", ""), DEFAULT_THEME)
    bg = Image.blend(bg, Image.new("RGB", (W, H), (10, 12, 16)), 0.55)
    bg = Image.blend(bg, Image.new("RGB", (W, H), tuple(c // 3 for c in color)), 0.28)   # 채널 색으로 물들임
    d = ImageDraw.Draw(bg)
    art = c.resize((440, 440), Image.LANCZOS)
    m = Image.new("L", art.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, 439, 439), radius=26, fill=255)
    bg.paste(art, (90, 140), m)
    x, tw = 580, W - 580 - 80
    d.ellipse((x, 150, x + 16, 166), fill=(255, 77, 94))
    d.text((x + 28, 144), "LIVE · 24H   yojosuknam Radio", font=font(FONT_B, 24), fill=(255, 255, 255))
    # 채널 배지: 색 점 + 채널 이름, 아래 한 줄 소개
    fb, ft = font(FONT_B, 26), font(FONT_R, 22)
    bw_ = int(d.textlength(label, font=fb)) + 64
    d.rounded_rectangle((x, 188, x + bw_, 232), radius=22, fill=tuple(c // 4 for c in color), outline=color, width=2)
    d.ellipse((x + 18, 202, x + 34, 218), fill=color)
    d.text((x + 46, 194), label, font=fb, fill=(255, 255, 255))
    d.text((x + bw_ + 16, 199), tagline, font=ft, fill=color)
    y = 250
    for line in wrap(d, now.get("title", ""), font(FONT_B, 50), tw, 3):
        d.text((x, y), line, font=font(FONT_B, 50), fill=(255, 255, 255))
        y += 64
    y += 6
    for line in wrap(d, now.get("album", ""), font(FONT_R, 28), tw, 2):
        d.text((x, y), line, font=font(FONT_R, 28), fill=(220, 226, 232))
        y += 38
    d.line((x, y + 10, x + 120, y + 10), fill=color, width=4)
    if nxt:
        d.text((x, 520), "다음 곡", font=font(FONT_B, 22), fill=(170, 180, 190))
        d.text((x, 550), wrap(d, nxt.get("title", ""), font(FONT_R, 26), tw, 1)[0],
               font=font(FONT_R, 26), fill=(230, 234, 238))
    d.text((90, 630), "music.yojosuknam.com/radio  ·  곡별 유튜브 링크·가사는 방송 페이지에서",
           font=font(FONT_R, 24), fill=(200, 208, 214))
    tmp = OUT / "frame.tmp.jpg"
    bg.save(tmp, quality=90)
    os.replace(tmp, FRAME)


class Schedule(threading.Thread):
    """nowplaying.json 을 읽어 지금 들리는 곡이 바뀌면 화면을 다시 그린다."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.items: list[dict] = []
        self.shown = ""

    def run(self) -> None:
        last_poll = 0.0
        while not stop.is_set():
            if time.time() - last_poll > 15:
                try:
                    d = json.loads(fetch(NOW_URL).decode("utf-8"))
                    seen = {x["at"]: x for x in self.items}
                    for x in [*(d.get("recent") or []), d.get("now"), *(d.get("next") or [])]:
                        if x:
                            seen[x["at"]] = x
                    self.items = sorted(seen.values(), key=lambda x: x["at"])[-20:]
                except Exception as e:  # noqa: BLE001
                    log(f"[경고] 지금 곡 정보 받기 실패({type(e).__name__})")
                last_poll = time.time()
            heard = (time.time() - AUDIO_LAG) * 1000
            cur = [i for i, x in enumerate(self.items) if x["at"] <= heard]
            if cur:
                i = cur[-1]
                key = f"{self.items[i]['at']}"
                if key != self.shown:
                    try:
                        render(self.items[i], self.items[i + 1] if i + 1 < len(self.items) else None)
                        self.shown = key
                        log(f"화면 ▶ {self.items[i]['title']}")
                    except Exception as e:  # noqa: BLE001
                        log(f"[경고] 화면 그리기 실패({type(e).__name__})")
            stop.wait(1)


def ffmpeg_cmd() -> list[str]:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
            "-re", "-f", "image2", "-loop", "1", "-framerate", str(FPS), "-i", str(FRAME),
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
            "-i", AUDIO,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-g", str(FPS * 2), "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-f", "flv", f"{RTMP}/{KEY}"]


def main() -> int:
    if not KEY:
        log("YOUTUBE_STREAM_KEY 가 없어 시작하지 않습니다 (radio.env 에 넣고 다시 켜세요)")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (W, H), (13, 15, 20)).save(FRAME)
    Schedule().start()
    backoff = 5
    while not stop.is_set():
        log("유튜브 송출 시작")
        t0 = time.time()
        p = subprocess.Popen(ffmpeg_cmd(), stdin=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for raw in p.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                log("  [ffmpeg] " + line)
        p.wait()
        backoff = 5 if time.time() - t0 > 300 else min(backoff * 2, 300)
        log(f"[경고] 유튜브 송출이 끊겼습니다(코드 {p.returncode}) — {backoff}초 뒤 다시")
        stop.wait(backoff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
