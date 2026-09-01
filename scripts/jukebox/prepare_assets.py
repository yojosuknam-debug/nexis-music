"""
2단계 — 커버 이미지 준비

catalog.json 의 앨범마다 정사각 커버 JPEG 를 만든다.
  * 라이브 유튜브 썸네일이 있으면 → 내려받아 가운데 정사각 크롭
  * 없으면 → 제목으로 타이포그래피 커버를 생성 (색은 제목 해시로 결정 = 앨범마다 고정)

출력: scripts/jukebox/assets/covers/<slug>.jpg  (800×800)

사용법:
    python scripts/jukebox/prepare_assets.py
    python scripts/jukebox/prepare_assets.py --force   # 이미 있어도 다시 만든다
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"
COVERS = HERE / "assets" / "covers"
# 커버가 유튜브 아트인지 자동 생성한 타이포인지 기록한다.
# catalog.json 은 scan 때마다 새로 만들어져 이 정보가 사라지므로 별도 파일에 남긴다.
META = COVERS / "_meta.json"
SIZE = 800

# 유튜브가 파이썬 UA 를 막는 경우가 있어 브라우저 UA 로 요청한다
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunsl.ttf",   # 맑은 고딕 Semilight — 한글·영문 모두 커버
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def square(im: Image.Image) -> Image.Image:
    w, h = im.size
    s = min(w, h)
    return im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize(
        (SIZE, SIZE), Image.LANCZOS)


def fetch_cover(url: str) -> Image.Image | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception:
        return None
    try:
        return square(Image.open(io.BytesIO(data)).convert("RGB"))
    except Exception:
        return None


def hue_of(seed: str) -> float:
    """제목 해시로 색상을 정한다 — 같은 앨범은 언제 다시 만들어도 같은 색."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return h[0] / 255.0


def wrap(draw, text: str, font, max_w: int) -> list[str]:
    """한국어는 공백 없이 길게 이어지는 경우가 많아 단어 단위로만 접으면 넘친다.
    단어로 먼저 접고, 그래도 넘치면 글자 단위로 자른다."""
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        if draw.textlength(word, font=font) <= max_w:
            cur = word
        else:
            chunk = ""
            for ch in word:
                if draw.textlength(chunk + ch, font=font) <= max_w:
                    chunk += ch
                else:
                    lines.append(chunk)
                    chunk = ch
            cur = chunk
    if cur:
        lines.append(cur)
    return lines[:4]


def make_placeholder(title: str, genre: str) -> Image.Image:
    """Aurora Glass 와 같은 어법 — 부드러운 색 번짐 위에 제목만."""
    hue = hue_of(title)
    base = Image.new("RGB", (SIZE, SIZE), "#0d0f14")
    blob = Image.new("RGB", (SIZE, SIZE), "#0d0f14")
    d = ImageDraw.Draw(blob)
    for i, (dx, dy, dh, rad) in enumerate([(0.28, 0.24, 0.0, 0.42),
                                           (0.74, 0.38, 0.09, 0.34),
                                           (0.46, 0.82, -0.07, 0.38)]):
        r, g, b = colorsys.hls_to_rgb((hue + dh) % 1.0, 0.44 + i * 0.05, 0.62)
        cx, cy, rr = dx * SIZE, dy * SIZE, rad * SIZE
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  fill=(int(r * 255), int(g * 255), int(b * 255)))
    blob = blob.filter(ImageFilter.GaussianBlur(radius=SIZE // 7))
    im = Image.blend(base, blob, 0.88)

    # 아래쪽을 어둡게 깔아 글씨가 항상 읽히게 한다
    veil = Image.new("L", (SIZE, SIZE), 0)
    vd = ImageDraw.Draw(veil)
    for y in range(SIZE):
        vd.line([(0, y), (SIZE, y)], fill=int(165 * (y / SIZE) ** 1.6))
    im = Image.composite(Image.new("RGB", (SIZE, SIZE), "#05060a"), im, veil)

    draw = ImageDraw.Draw(im)
    margin = 64
    font = pick_font(72)
    lines = wrap(draw, title, font, SIZE - margin * 2)
    while len(lines) > 3 and font.size > 40:
        font = pick_font(font.size - 8)
        lines = wrap(draw, title, font, SIZE - margin * 2)

    lh = int(font.size * 1.22)
    y = SIZE - margin - lh * len(lines)
    if genre:
        gfont = pick_font(24)
        g = genre.split("/")[0].strip()[:28].upper()
        draw.text((margin, y - 46), g, font=gfont, fill=(255, 255, 255, 150))
    for ln in lines:
        draw.text((margin, y), ln, font=font, fill="white")
        y += lh
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not CATALOG.exists():
        print("[에러] catalog.json 이 없습니다. scan_albums.py 를 먼저 실행하세요.")
        return 1

    albums = json.loads(CATALOG.read_text(encoding="utf-8"))
    COVERS.mkdir(parents=True, exist_ok=True)
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}

    made = {"downloaded": 0, "generated": 0, "skipped": 0, "upgraded": 0, "failed": []}
    for a in albums:
        slug, src = a["slug"], a.get("cover_source", "")
        out = COVERS / f"{slug}.jpg"
        rec = meta.get(slug)
        if rec is None and out.exists():
            # 기록이 없는 예전 커버 — 타이포는 유튜브 주소가 없을 때만 만들어지므로 이렇게 추정할 수 있다
            rec = {"kind": "youtube" if src else "generated", "src": src}

        if out.exists() and not args.force:
            upgradable = rec and rec.get("kind") == "generated" and src
            changed = rec and rec.get("kind") == "youtube" and src and rec.get("src") != src
            if not (upgradable or changed):
                made["skipped"] += 1
                a["cover_file"] = out.name
                meta[slug] = rec or {"kind": "generated", "src": src}
                continue
            # 타이포 커버였는데 유튜브 아트가 생겼다 → 이제 진짜 커버로 바꾼다

        im = fetch_cover(src) if src else None
        if im is not None:
            if out.exists() and rec and rec.get("kind") == "generated":
                made["upgraded"] += 1
            else:
                made["downloaded"] += 1
            kind = "youtube"
        else:
            if src:
                made["failed"].append(a["folder"])          # 주소는 있었는데 못 받은 경우
            im = make_placeholder(a["title"], a.get("genre", ""))
            made["generated"] += 1
            kind = "generated"

        im.save(out, "JPEG", quality=86, optimize=True)
        a["cover_file"] = out.name
        meta[slug] = {"kind": kind, "src": src}

    CATALOG.write_text(json.dumps(albums, ensure_ascii=False, indent=1), encoding="utf-8")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(f.stat().st_size for f in COVERS.glob("*.jpg"))
    print(f"커버 {len(albums)}장")
    print(f"  유튜브에서 내려받음  {made['downloaded']:>3}")
    print(f"  타이포 → 유튜브 교체 {made['upgraded']:>3}")
    print(f"  타이포로 생성        {made['generated']:>3}")
    print(f"  이미 있어 건너뜀     {made['skipped']:>3}")
    if made["failed"]:
        print(f"  ⚠️ 주소는 있으나 실패: {', '.join(made['failed'])}")
    print(f"  합계 {total//1024}KB → {COVERS.relative_to(HERE.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
