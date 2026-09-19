"""
Create designed fallback covers for albums without miniPC project thumbnails.

These are used only after checking that no finished project thumbnail exists.
The output is the same 800x800 JPEG format used by the jukebox covers.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
COVERS = HERE / "assets" / "covers"
META = COVERS / "_meta.json"
SIZE = 800

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunsl.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [r"C:\Windows\Fonts\malgunbd.ttf"] + FONT_CANDIDATES if bold else FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_center(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt, fill) -> None:
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=fnt, fill=fill)


def save(im: Image.Image, slug: str, note: str) -> None:
    out = COVERS / f"{slug}.jpg"
    im.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    meta[slug] = {"kind": "designed_cover", "src": note}
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


def neon_hours() -> Image.Image:
    im = Image.new("RGB", (SIZE, SIZE), "#070915")
    draw = ImageDraw.Draw(im, "RGBA")

    for y in range(SIZE):
        r = int(8 + 35 * y / SIZE)
        g = int(10 + 8 * math.sin(y / 70))
        b = int(28 + 80 * (1 - y / SIZE))
        draw.line((0, y, SIZE, y), fill=(r, g, b, 255))

    # River reflection and skyline
    draw.rectangle((0, 430, SIZE, SIZE), fill=(8, 16, 34, 220))
    for x in range(40, SIZE, 70):
        h = 120 + (x * 37) % 190
        color = (25, 33, 62, 240)
        draw.rectangle((x, 410 - h, x + 42, 430), fill=color)
        for wy in range(410 - h + 18, 420, 32):
            draw.rectangle((x + 10, wy, x + 18, wy + 6), fill=(0, 220, 255, 120))

    for x in range(-220, 980, 28):
        draw.line((400, 480, x, 800), fill=(0, 229, 255, 45), width=1)
    for y in range(500, 800, 34):
        draw.line((0, y, SIZE, y), fill=(255, 53, 185, 38), width=1)

    for x, y, c in [
        (160, 170, (255, 43, 177, 210)),
        (650, 220, (0, 224, 255, 190)),
        (510, 585, (255, 189, 59, 120)),
    ]:
        draw.ellipse((x - 120, y - 120, x + 120, y + 120), fill=c)
    im = im.filter(ImageFilter.GaussianBlur(10))
    draw = ImageDraw.Draw(im, "RGBA")

    title = font(74, True)
    sub = font(30)
    draw.text((66, 108), "NEON_HOURS", font=title, fill=(255, 255, 255, 245))
    draw.text((70, 190), "네온 아워스", font=sub, fill=(132, 245, 255, 230))
    draw.line((70, 245, 520, 245), fill=(255, 45, 190, 180), width=5)
    draw.text((72, 650), "K-URBAN POP  ·  NIGHT DRIVE", font=font(25), fill=(255, 255, 255, 190))
    return im


def pansori(vol: int) -> Image.Image:
    warm = vol == 1
    bg = "#d7c29a" if warm else "#c8cad7"
    im = Image.new("RGB", (SIZE, SIZE), bg)
    noise = Image.effect_noise((SIZE, SIZE), 18).convert("L")
    im = Image.composite(Image.new("RGB", (SIZE, SIZE), "#f3ead5" if warm else "#e5e8f1"), im, noise)
    draw = ImageDraw.Draw(im, "RGBA")

    accent = (160, 41, 28, 210) if warm else (38, 73, 148, 210)
    ink = (36, 31, 26, 235) if warm else (28, 31, 48, 235)

    # Triptych panels
    panel_w = 190
    for i, x in enumerate([80, 305, 530]):
        draw.rounded_rectangle((x, 170, x + panel_w, 545), radius=8, outline=(70, 55, 40, 100), width=3)
        wash = (96, 77, 54, 32) if warm else (38, 55, 93, 32)
        draw.ellipse((x + 28, 225, x + 162, 455), fill=wash)
        draw.line((x + 42, 460, x + 150, 282), fill=ink, width=5)
        draw.arc((x + 42, 260, x + 152, 460), 210, 330, fill=ink, width=4)
        if i == 1:
            draw.line((x + 96, 230, x + 96, 480), fill=ink, width=6)
            draw.line((x + 56, 360, x + 136, 330), fill=accent, width=5)
        if i == 2:
            draw.arc((x + 42, 270, x + 160, 450), 20, 155, fill=accent, width=5)

    # Brush stroke
    for off in range(16):
        draw.arc((72 - off, 574 - off, 728 + off, 755 + off), 184, 345, fill=accent, width=2)

    top = "성서 판소리 제일집" if vol == 1 else "성서 판소리 제이집"
    en = "BIBLE PANSORI VOL.1" if vol == 1 else "BIBLE PANSORI VOL.2"
    text_center(draw, (400, 75), top, font(56, True), ink)
    text_center(draw, (400, 126), "세 이야기", font(29), (*ink[:3], 210))
    text_center(draw, (400, 642), en, font(35, True), ink)
    text_center(draw, (400, 692), "THREE SACRED TALES", font(25), (*ink[:3], 210))
    return im


def main() -> int:
    save(neon_hours(), "neon_hours-네온-아워스", "designed from NEON_HOURS_album.md cover prompt")
    save(pansori(1), "bible-pansori-vol-1-three-sacred-tales", "designed from bible_pansori_vol1_album.md cover prompt")
    save(pansori(2), "bible-pansori-vol-2-three-sacred-tales", "designed from bible_pansori_vol2_album.md cover prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
