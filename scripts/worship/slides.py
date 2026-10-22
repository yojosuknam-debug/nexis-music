"""
예배 화면 — 교회 프로젝터 자막 스타일 슬라이드(1920×1080)를 코드로 그린다.

    python scripts/worship/slides.py output/worship/2026-10-22_ko     # 견본 3장(봉독·말씀·찬양) → <폴더>/slides_sample/

공통: 잔잔한 배경(1분 묵상 주제 이미지, 어둡게+흐리게) · 위 왼쪽 예배 이름·날짜 · 아래 주보 순서 띠(지금 순서 밝게) ·
      맨 아래 'AI의 도움으로 준비' 표기.
글꼴 = fonts/ 의 고운바탕(말씀·제목)·Pretendard(자막·메뉴) — 둘 다 SIL OFL.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
BG_DIR = Path(os.environ.get("WORSHIP_BG_DIR", r"D:\YH\APP\autovid\assets\qt_images"))   # 1분 묵상 주제 배경
W, H = 1920, 1080
GOLD = (226, 196, 128)
WHITE = (250, 247, 240)
DIM = (170, 165, 155)
UA = "Mozilla/5.0 NexisWorship/1.0"

LABELS = {
    "ko": {"service": "말씀 묵상 예배", "ai": "설교와 기도는 AI의 도움으로 준비되었습니다 · 말씀Log",
           "order": [("call", "부름"), ("song1", "찬양"), ("prayer", "기도"), ("reading", "봉독"), ("sermon", "말씀"),
                     ("closing", "결단 기도"), ("song2", "응답 찬양"), ("lords_prayer", "주기도문"), ("blessing", "축복")],
           "sermon": "말씀", "song": "찬양", "qr": "원곡 듣기"},
    "en": {"service": "Worship in the Word", "ai": "Sermon and prayers prepared with the help of AI · Malsseum Log",
           "order": [("call", "Call"), ("song1", "Praise"), ("prayer", "Prayer"), ("reading", "Scripture"),
                     ("sermon", "Sermon"), ("closing", "Response"), ("song2", "Song"), ("lords_prayer", "Lord's Prayer"),
                     ("blessing", "Blessing")],
           "sermon": "Sermon", "song": "Praise", "qr": "Listen"},
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


SERIF, SERIF_B = "GowunBatang-Regular", "GowunBatang-Bold"
SANS, SANS_B = "Pretendard-Regular", "Pretendard-Bold"


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """띄어쓰기 단위 줄바꿈(한글은 어절을 쪼개지 않는다)."""
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if f.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def background(img: Image.Image | Path, darken: float = 0.55, blur: int = 6) -> Image.Image:
    im = Image.open(img) if isinstance(img, Path) else img
    im = im.convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(blur))
    shade = Image.new("RGB", (W, H), (12, 14, 20))
    im = Image.blend(im, shade, darken)
    # 아래·위를 조금 더 어둡게(글자 띠가 읽히게)
    grad = Image.new("L", (1, H))
    for yy in range(H):
        edge = max(0.0, 1 - min(yy, H - yy) / 260)
        grad.putpixel((0, yy), int(150 * edge))
    im.paste(Image.new("RGB", (W, H), (8, 9, 12)), (0, 0), grad.resize((W, H)))
    return im


def chrome(im: Image.Image, lang: str, date: str, current: str) -> ImageDraw.ImageDraw:
    """위: 예배 이름·날짜 / 아래: 주보 순서 띠 / 맨 아래: AI 표기."""
    L = LABELS[lang]
    d = ImageDraw.Draw(im)
    d.text((72, 52), L["service"], font=font(SERIF_B, 34), fill=GOLD)
    d.text((72 + font(SERIF_B, 34).getlength(L["service"]) + 22, 60), date.replace("-", ". "),
           font=font(SANS, 24), fill=DIM)
    items = L["order"]
    f, fb = font(SANS, 25), font(SANS_B, 25)
    widths = [(fb if k == current else f).getlength(t) for k, t in items]
    gap = 46
    x = (W - (sum(widths) + gap * (len(items) - 1))) // 2
    y = H - 118
    done = True
    for (k, t), w in zip(items, widths):
        if k == current:
            done = False
            d.text((x, y), t, font=fb, fill=WHITE)
            d.rounded_rectangle((x - 2, y + 40, x + w + 2, y + 44), 2, fill=GOLD)
        else:
            d.text((x, y), t, font=f, fill=(150, 146, 138) if done else (110, 108, 104))
        x += w + gap
    fa = font(SANS, 19)
    d.text(((W - fa.getlength(L["ai"])) // 2, H - 52), L["ai"], font=fa, fill=(120, 117, 110))
    return d


def centered(d: ImageDraw.ImageDraw, lines: list[str], f, cy: int, fill, spacing: float = 1.55) -> None:
    lh = int(f.size * spacing)
    y = cy - lh * len(lines) // 2
    for ln in lines:
        d.text(((W - f.getlength(ln)) // 2, y), ln, font=f, fill=fill)
        y += lh


# ── 화면 종류 ─────────────────────────────────────────────────────────────
def scripture(lang: str, date: str, ref: str, text: str, bg: Path) -> Image.Image:
    """성경 봉독 — 한 절씩 큰 명조. 말씀이 화면의 주인공."""
    im = background(bg, 0.62, 8)
    d = chrome(im, lang, date, "reading")
    fr = font(SANS_B, 34)
    f = font(SERIF, 66 if lang == "ko" else 60)
    lines = wrap(text, f, 1380)
    while len(lines) > 5:
        f = font(SERIF, f.size - 4)
        lines = wrap(text, f, 1380)
    block = int(f.size * 1.6) * len(lines)
    top = 540 - block // 2 - 40
    d.text(((W - fr.getlength(ref)) // 2, top - 70), ref, font=fr, fill=GOLD)
    centered(d, lines, f, 540 - 20, WHITE, 1.6)
    return im


def sermon(lang: str, date: str, title: str, sentence: str, bg: Path, point: str = "") -> Image.Image:
    """말씀 — 위에 설교 제목(명조), 아래 지금 문장 자막(고딕, 반투명 띠)."""
    return caption(lang, date, "sermon", LABELS[lang]["sermon"] + (f"  ·  {point}" if point else ""), title, sentence, bg)


def caption(lang: str, date: str, current: str, label: str, title: str, sentence: str, bg: Path) -> Image.Image:
    """자막 화면(부름·기도·말씀·주기도문·축복) — 위에 순서 제목(명조), 아래 지금 문장(고딕, 반투명 띠)."""
    im = background(bg, 0.5, 4)
    d = chrome(im, lang, date, current)
    ft = font(SERIF_B, 64)
    while ft.getlength(title) > 1600:
        ft = font(SERIF_B, ft.size - 4)
    d.text(((W - ft.getlength(title)) // 2, 300), title, font=ft, fill=WHITE)
    lab = label
    fl = font(SANS, 28)
    d.text(((W - fl.getlength(lab)) // 2, 252), lab, font=fl, fill=GOLD)
    d.rounded_rectangle((W // 2 - 60, 404, W // 2 + 60, 407), 2, fill=GOLD)
    fs = font(SANS_B, 50 if lang == "ko" else 46)
    lines = wrap(sentence, fs, 1500)[:3]
    lh = int(fs.size * 1.5)
    box_h = lh * len(lines) + 70
    y0 = 800 - box_h
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle((170, y0, W - 170, y0 + box_h), 22, fill=(10, 10, 14, 150))
    im.paste(band, (0, 0), band)
    d = ImageDraw.Draw(im)
    y = y0 + 35
    for ln in lines:
        d.text(((W - fs.getlength(ln)) // 2, y), ln, font=fs, fill=WHITE)
        y += lh
    return im


def qr_image(url: str, px: int) -> Image.Image | None:
    try:
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=2, dark="#111111", light="#faf7f0")
    return Image.open(buf).convert("RGB").resize((px, px), Image.NEAREST)


def song(lang: str, date: str, part: str, title: str, lines: list[str], bg: Path, url: str = "") -> Image.Image:
    """찬양 — 교회 프로젝터 가사 화면: 가운데 큰 가사 두 줄, 위에 곡 제목, 오른쪽 아래 원곡 QR.
    앨범 표지는 쓰지 않는다 — 표지가 1번 곡 쇼츠 썸네일이라 다른 곡 제목이 박혀 있다(10-23 확인)."""
    im = background(bg, 0.62, 10)
    d = chrome(im, lang, date, part)
    main, sub = (re.match(r"^(.*?)\s*\((.*)\)\s*$", title) or re.match(r"^(.*)$()", title)).groups()
    head = f"{LABELS[lang]['song']}  ·  {main if lang == 'ko' or not sub else sub}"
    fh = font(SANS, 30)
    d.text(((W - fh.getlength(head)) // 2, 250), head, font=fh, fill=GOLD)
    d.rounded_rectangle((W // 2 - 60, 302, W // 2 + 60, 305), 2, fill=GOLD)
    f = font(SANS_B, 70)
    shown = []
    for ln in lines[:2]:
        shown += wrap(ln, f, 1500)
    centered(d, shown[:3], f, 560, WHITE, 1.55)
    if url:
        q = qr_image(url, 150)
        if q:
            im.paste(q, (W - 150 - 90, H - 150 - 170))
            fq = font(SANS, 20)
            d.text((W - 90 - 75 - fq.getlength(LABELS[lang]["qr"]) // 2, H - 168), LABELS[lang]["qr"], font=fq, fill=DIM)
    return im


# ── 보조 ──────────────────────────────────────────────────────────────────
TOPIC_WORDS = {
    "감사": "감사", "겸손": "겸손", "구원": "구원", "기도": "기도", "믿음": "믿음", "복음": "복음", "사랑": "사랑",
    "섬김": "섬김", "성령": "성령", "소망": "소망", "순종": "순종", "예배": "예배", "용서": "용서", "은혜": "은혜",
    "인내": "인내", "지혜": "지혜", "치유": "치유", "평안": "평안", "회개": "회개", "따르": "순종", "생수": "은혜",
}


def topic_bg(text: str) -> Path:
    for w, name in TOPIC_WORDS.items():
        if w in text:
            return BG_DIR / f"{name}.png"
    return BG_DIR / "평안.png"


def fetch(url: str) -> bytes:
    p = urllib.parse.urlsplit(url)
    url = p._replace(path=urllib.parse.quote(p.path)).geturl()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return r.read()


def song_lyrics(page: str, n: int) -> list[dict]:
    """앨범 페이지 가사 → 두 줄씩 [{start, end, lines}] (초).
    가사는 [{'tag': '0:14-0:42', 'lines': [...]}, ...] — 시간 꼬리표가 붙은 구간만 시각을 알 수 있어
    그 구간 안에서 두 줄씩 고르게 나눈다. 곡 번호는 문자열("2")로 저장돼 있다."""
    html = fetch(page).decode("utf-8")
    m = re.search(r"window\.ALBUM\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    for t in json.loads(m.group(1)).get("tracks", []) if m else []:
        if str(t.get("n")) != str(n):
            continue
        out = []
        for sec in t.get("lyrics") or []:
            if not isinstance(sec, dict):
                continue
            tm = re.match(r"^\s*(\d+):(\d\d)\s*-\s*(\d+):(\d\d)\s*$", sec.get("tag", ""))
            lines = [ln.strip() for ln in sec.get("lines") or [] if ln.strip() and not re.match(r"^[\[(]", ln.strip())]
            if not tm or not lines:
                continue
            a = int(tm.group(1)) * 60 + int(tm.group(2))
            b = int(tm.group(3)) * 60 + int(tm.group(4))
            pairs = [lines[i:i + 2] for i in range(0, len(lines), 2)]
            step = (b - a) / len(pairs)
            out += [{"start": a + i * step, "end": a + (i + 1) * step, "lines": p} for i, p in enumerate(pairs)]
        return out
    return []


def sample(folder: Path) -> None:
    s = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    lang, date = s["lang"], s["date"]
    dst = folder / "slides_sample"
    dst.mkdir(exist_ok=True)
    v = s["verses"][2] if len(s["verses"]) > 2 else s["verses"][0]
    scripture(lang, date, v["reference"], re.sub(r"[()]", "", v["text"]), BG_DIR / "말씀.png").save(dst / "1_봉독.png")
    ser = next(p for p in s["parts"] if p["id"] == "sermon")
    sents = re.split(r"(?<=[.!?])\s+", ser["text"])
    sermon(lang, date, ser["title"], sents[min(14, len(sents) - 1)], topic_bg(s["title"] + ser["text"][:400]),
           "와 보라" if lang == "ko" else "").save(dst / "2_말씀.png")
    sp = next(p for p in s["parts"] if p["id"] == "song1")["song"]
    ly = song_lyrics(sp["page"], sp["n"])
    song(lang, date, "song1", sp["title"], ly[1]["lines"] if len(ly) > 1 else [], BG_DIR / "예배.png",
         sp.get("youtube", "")).save(dst / "3_찬양.png")
    print("견본 →", dst)


if __name__ == "__main__":
    sample(Path(sys.argv[1]))
