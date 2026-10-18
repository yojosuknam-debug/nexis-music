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
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import segno          # 곡별 원곡 영상 QR (없으면 QR 없이 그린다)
except ImportError:
    segno = None

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


def clean(text: str) -> str:
    """나눔고딕에 없는 이모지(🎹 ⭐ 등)를 뺀다 — 그대로 그리면 ☒ 로 나온다."""
    keep = (ch for ch in text if not (ord(ch) >= 0x1F000 or 0x2600 <= ord(ch) <= 0x27BF
                                       or 0x2B00 <= ord(ch) <= 0x2BFF or ch in "️‍"))
    return " ".join("".join(keep).split())


def split_title(title: str) -> tuple[str, str]:
    """'회전목마의 꿈 (Carousel Dream)' → ('회전목마의 꿈', 'Carousel Dream'). 괄호가 없으면 그대로."""
    if title.endswith(")") and " (" in title:
        main, sub = title.rsplit(" (", 1)
        if main.strip():
            return main.strip(), sub[:-1].strip()
    return title, ""


RADIO_PAGE = "https://music.yojosuknam.com/radio"


def short_yt(url: str) -> str:
    """watch?v=ID&t=1002s → https://youtu.be/ID?t=1002 (QR 칸 수를 줄여 화면에서 잘 찍히게). 링크 없으면 방송 페이지."""
    m = re.search(r"[?&]v=([\w-]{11})", url or "")
    if not m:
        return RADIO_PAGE
    t = re.search(r"[?&]t=(\d+)", url)
    return f"https://youtu.be/{m.group(1)}" + (f"?t={t.group(1)}" if t and t.group(1) != "0" else "")


def draw_qr(bg: Image.Image, url: str, x: int, y: int, size: int) -> None:
    """흰 둥근 판 위에 QR. 칸은 정수 픽셀로 맞춰 영상 압축에도 또렷하게."""
    if segno is None:
        return
    rows = [list(r) for r in segno.make(url, error="m", micro=False).matrix]
    n = len(rows)
    cell = max(2, (size - 16) // n)
    q = n * cell
    pad = (size - q) // 2
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle((x, y, x + size, y + size), radius=12, fill=(255, 255, 255))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v:
                d.rectangle((x + pad + c * cell, y + pad + r * cell,
                             x + pad + (c + 1) * cell - 1, y + pad + (r + 1) * cell - 1), fill=(12, 14, 18))


_cover_cache: dict[str, Image.Image] = {}


def cover(url: str) -> Image.Image:
    if url not in _cover_cache:
        try:
            _cover_cache.clear()
            _cover_cache[url] = Image.open(io.BytesIO(fetch(url))).convert("RGB")
        except Exception:  # noqa: BLE001
            _cover_cache[url] = Image.new("RGB", (800, 800), (40, 46, 58))
    return _cover_cache[url]


# ───────── 가사 (곡이 바뀔 때마다 앨범 페이지의 window.ALBUM 에서 읽는다) ─────────
_album_cache: dict[str, dict] = {}
NOTE = re.compile(r"^[(\[].*[)\]]$")              # 줄 전체가 (연주 메모)·[구간 표시]
LEAD = re.compile(r"^\s*(?:\[[^\]]*\]|\([^)]*\))\s*")   # 줄 앞 [Male]·(Heung) 같은 표시


def album_data(page: str) -> dict:
    if page and page not in _album_cache:
        try:
            html = fetch(urllib.parse.quote(page, safe=":/?=&%#")).decode("utf-8")
            m = re.search(r"window\.ALBUM = (\{.*?\});</script>", html)
            if len(_album_cache) > 8:
                _album_cache.clear()
            _album_cache[page] = json.loads(m.group(1)) if m else {}
        except Exception as e:  # noqa: BLE001  — 실패는 저장 안 함(다음 곡 때 다시)
            log(f"[경고] 가사 받기 실패({type(e).__name__})")
            return {}
    return _album_cache.get(page, {})


def lyric_lines(now: dict) -> list[str]:
    """부르는 가사 줄만. 구간 사이는 '' 한 줄. 연주 메모만 있는 곡·4줄 미만은 [] (= 가사 없는 화면)."""
    t = next((t for t in album_data(now.get("page", "")).get("tracks", [])
              if str(t.get("n")) == str(now.get("n"))), None)
    if not t or t.get("instrumental"):
        return []
    out: list[str] = []
    for sec in t.get("lyrics") or []:
        got = []
        for line in sec.get("lines") or []:
            line = clean(line)
            if NOTE.match(line):
                continue
            while LEAD.match(line) and LEAD.sub("", line, count=1) != line:
                line = LEAD.sub("", line, count=1)
            if line:
                got.append(line)
        if got:
            out += ([""] if out else []) + got
    return out if sum(1 for x in out if x) >= 4 else []


PANEL = (90, 140, 530, 580)     # 큰 표지 자리 → 가사 칸


class Lyrics:
    """가사 전체를 긴 띠(글자 마스크)로 한 번 그려 두고, 곡 진행에 맞춰 창만 내린다.
    전주(약 8%, 최대 15초) 동안은 첫 줄에 머물고, 끝(약 10%, 최대 20초)엔 마지막 줄에서 멈춘다."""
    LH, GAP = 36, 16

    def __init__(self, lines: list[str], ms: int) -> None:
        x0, y0, x1, y1 = PANEL
        self.wx, self.wy = x0 + 30, y0 + 58
        self.ww, self.wh = (x1 - 30) - self.wx, (y1 - 18) - self.wy
        f = font(FONT_R, 23)
        d = ImageDraw.Draw(Image.new("L", (1, 1)))
        rows: list[tuple[str, int] | None] = []     # (글, 들여쓰기) — 넘어간 줄은 조금 들여 쓴다
        for line in lines:
            if not line:
                rows.append(None)
                continue
            if d.textlength(line, font=f) <= self.ww:
                rows.append((line, 0))
            else:
                parts = wrap(d, line, f, self.ww - 18, 3)
                rows += [(parts[0], 0)] + [(part, 18) for part in parts[1:]]
        self.focal = int(self.wh * 0.40)
        hgt = sum(self.GAP if r is None else self.LH for r in rows)
        self.strip = Image.new("L", (self.ww, hgt + 2 * self.wh), 0)
        sd, y = ImageDraw.Draw(self.strip), self.wh
        for r in rows:
            if r is None:
                y += self.GAP
                continue
            sd.text((r[1], y + 6), r[0], font=f, fill=255)
            y += self.LH
        self.first, self.last = self.LH // 2, max(self.LH // 2, hgt - self.LH // 2)
        self.ms = max(ms, 30000)
        # 가운데(지금 읽는 높이) 밝게, 위·아래로 갈수록 흐리게
        self.fade = Image.new("L", (self.ww, self.wh))
        fd = ImageDraw.Draw(self.fade)
        for yy in range(self.wh):
            dist = abs(yy - self.focal) / max(self.focal, self.wh - self.focal)
            a = 255 if dist < 0.12 else int(255 - (dist - 0.12) / 0.88 * 200)
            edge = min(yy, self.wh - 1 - yy)
            a = int(a * min(1.0, edge / 56))
            fd.line((0, yy, self.ww, yy), fill=max(0, a))

    def frame(self, base: Image.Image, elapsed_ms: float) -> Image.Image:
        t0 = min(15000, self.ms * 0.08)
        t1 = self.ms - min(20000, self.ms * 0.10)
        p = min(1.0, max(0.0, (elapsed_ms - t0) / max(1.0, t1 - t0)))
        o = self.first + p * (self.last - self.first)
        top = int(self.wh + o - self.focal)
        win = self.strip.crop((0, top, self.ww, top + self.wh))
        img = base.copy()
        img.paste((244, 246, 250), (self.wx, self.wy, self.wx + self.ww, self.wy + self.wh),
                  ImageChops.multiply(win, self.fade))
        return img


def save(img: Image.Image) -> None:
    tmp = OUT / "frame.tmp.jpg"
    img.save(tmp, quality=88)
    os.replace(tmp, FRAME)


def render(now: dict, nxt: dict | None) -> tuple[Image.Image, Lyrics | None]:
    """곡 하나의 바탕 화면을 그린다. 가사가 있으면 표지 자리를 가사 칸으로 비워 두고 Lyrics 를 돌려준다."""
    c = cover(now.get("cover", ""))
    lines = lyric_lines(now)
    lyr = Lyrics(lines, int(now.get("ms") or 0)) if lines else None
    bg = c.resize((W, W)).crop((0, (W - H) // 2, W, (W + H) // 2)).filter(ImageFilter.GaussianBlur(40))
    color, label, tagline = THEMES.get(now.get("station", ""), DEFAULT_THEME)
    bg = Image.blend(bg, Image.new("RGB", (W, H), (10, 12, 16)), 0.55)
    bg = Image.blend(bg, Image.new("RGB", (W, H), tuple(c // 3 for c in color)), 0.28)   # 채널 색으로 물들임
    d = ImageDraw.Draw(bg)
    x0, y0, x1, y1 = PANEL
    if lyr:
        # 가사 칸: 어두운 반투명 판 + 위에 '가사' 표시
        m = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=26, fill=150)
        bg.paste((8, 10, 14), (x0, y0, x1, y1), m)
        d.text((x0 + 30, y0 + 20), "가사", font=font(FONT_B, 18), fill=color)
        d.text((x0 + 76, y0 + 21), "LYRICS", font=font(FONT_R, 16), fill=(130, 140, 152))
    else:
        art = c.resize((x1 - x0, y1 - y0), Image.LANCZOS)
        m = Image.new("L", art.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, art.width - 1, art.height - 1), radius=26, fill=255)
        bg.paste(art, (x0, y0), m)
    x, tw = 580, W - 580 - 80
    # 맨 위(표지 윗선 140 에 맞춤): LIVE 줄 → 채널 배지 + 한 줄 소개
    d.ellipse((x, 148, x + 14, 162), fill=(255, 77, 94))
    d.text((x + 26, 141), "LIVE · 24H  ·  yojosuknam Radio", font=font(FONT_B, 22), fill=(236, 240, 244))
    fb, ft = font(FONT_B, 22), font(FONT_R, 20)
    bw_ = int(d.textlength(label, font=fb)) + 54
    d.rounded_rectangle((x, 182, x + bw_, 218), radius=18, fill=tuple(c // 4 for c in color), outline=color, width=2)
    d.ellipse((x + 16, 194, x + 28, 206), fill=color)
    d.text((x + 38, 187), label, font=fb, fill=(255, 255, 255))
    d.text((x + bw_ + 14, 189), wrap(d, tagline, ft, tw - bw_ - 14, 1)[0], font=ft, fill=color)

    # 가운데: 곡 제목(한글) / 괄호 속 영어 제목 / 앨범 — 블록 전체를 배지와 구분선 사이 가운데에
    main, sub = split_title(clean(now.get("title", "")))
    album = clean(now.get("album", ""))
    ftt, fsub, falb = font(FONT_B, 48), font(FONT_R, 28), font(FONT_R, 22)
    tl = wrap(d, main, ftt, tw, 2)
    sl = wrap(d, sub, fsub, tw, 1) if sub else []
    th = 64 if lyr else 0                        # 가사 화면이면 앨범 줄에 작은 표지
    al = wrap(d, album, falb, tw - (th + 16 if th else 46), 1) if album else []
    block = len(tl) * 60 + (10 + len(sl) * 38 if sl else 0) + ((22 + (th or 30)) if al or th else 0)
    y = 236 + max(0, (480 - 236 - block) // 2)
    for line in tl:
        d.text((x, y), line, font=ftt, fill=(255, 255, 255))
        y += 60
    if sl:
        y += 10
        for line in sl:
            d.text((x, y), line, font=fsub, fill=(206, 212, 220))
            y += 38
    if th:
        y += 22
        art = c.resize((th, th), Image.LANCZOS)
        m = Image.new("L", art.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, th - 1, th - 1), radius=10, fill=255)
        bg.paste(art, (x, y), m)
        d.text((x + th + 16, y + 6), "앨범", font=font(FONT_B, 18), fill=color)
        if al:
            d.text((x + th + 16, y + 32), al[0], font=falb, fill=(170, 178, 188))
    elif al:
        y += 22
        d.text((x, y + 1), "앨범", font=font(FONT_B, 18), fill=color)
        d.text((x + 46, y), al[0], font=falb, fill=(170, 178, 188))

    # 아래(표지 아랫선 580 에 맞춤): 구분선 → 다음 곡
    d.line((x, 498, x + tw, 498), fill=tuple(min(255, c // 2 + 30) for c in color), width=1)
    # 오른쪽 아래: 지금 곡 원곡 영상 QR (화면은 클릭이 안 되니 폰으로 찍게)
    qs, nw = 132, tw
    if segno is not None:
        qx, qy = x + tw - qs, 512
        draw_qr(bg, short_yt(now.get("youtube", "")), qx, qy, qs)
        cap = "이 곡 원곡 영상" if "youtu" in (now.get("youtube") or "") else "곡별 링크 모음"
        fc = font(FONT_R, 16)
        d.text((qx + (qs - d.textlength(cap, font=fc)) / 2, qy + qs + 8), cap, font=fc, fill=(170, 178, 188))
        nw = tw - qs - 24
    if nxt:
        d.text((x, 516), "다음 곡", font=font(FONT_B, 18), fill=(150, 160, 172))
        n_main, n_sub = split_title(clean(nxt.get("title", "")))
        fn, fns = font(FONT_R, 26), font(FONT_R, 20)
        n_main = wrap(d, n_main, fn, nw, 1)[0]
        d.text((x, 544), n_main, font=fn, fill=(230, 234, 238))
        if n_sub:
            nx = x + int(d.textlength(n_main, font=fn)) + 12
            if nx < x + nw - 60:
                d.text((nx, 550), wrap(d, n_sub, fns, x + nw - nx, 1)[0], font=fns, fill=(150, 160, 172))
    d.text((90, 630), "music.yojosuknam.com/radio  ·  곡별 유튜브 링크·가사는 방송 페이지에서",
           font=font(FONT_R, 24), fill=(200, 208, 214))
    return bg, lyr


class Schedule(threading.Thread):
    """nowplaying.json 을 읽어 지금 들리는 곡이 바뀌면 화면을 다시 그린다."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.items: list[dict] = []
        self.shown = ""
        self.base: Image.Image | None = None
        self.lyr: Lyrics | None = None
        self.at = 0
        self.fails = 0

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
                        self.base, self.lyr = render(self.items[i], self.items[i + 1] if i + 1 < len(self.items) else None)
                        self.at = self.items[i]["at"]
                        if not self.lyr:
                            save(self.base)
                        self.shown = key
                        log(f"화면 ▶ {self.items[i]['title']}" + (" (가사)" if self.lyr else ""))
                    except Exception as e:  # noqa: BLE001
                        self.lyr = None
                        log(f"[경고] 화면 그리기 실패({type(e).__name__})")
                if self.lyr:
                    try:
                        save(self.lyr.frame(self.base, heard - self.at))
                        self.fails = 0
                    except Exception as e:  # noqa: BLE001  — 한두 번은 건너뛰고, 계속 실패하면 표지 화면으로
                        self.fails += 1
                        if self.fails == 1:
                            log(f"[경고] 가사 그리기 실패({type(e).__name__})")
                        if self.fails >= 50:
                            self.lyr = None
                            log("[경고] 가사 그리기 계속 실패 — 이 곡은 가사 칸 멈춘 채로")
            stop.wait(1 / FPS if self.lyr else 1)


def ffmpeg_cmd() -> list[str]:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
            "-re", "-f", "image2", "-loop", "1", "-framerate", str(FPS), "-i", str(FRAME),
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
            "-i", AUDIO,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
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
