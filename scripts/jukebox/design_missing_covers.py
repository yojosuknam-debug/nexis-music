"""
Create designed fallback covers for albums without miniPC project thumbnails.

These are used only after checking that no finished project thumbnail exists.
The output is the same 800x800 JPEG format used by the jukebox covers.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
    im = Image.new("RGB", (SIZE, SIZE), "#080b14")
    draw = ImageDraw.Draw(im, "RGBA")

    for y in range(SIZE):
        r = int(7 + 10 * y / SIZE)
        g = int(9 + 12 * y / SIZE)
        b = int(22 + 24 * (1 - y / SIZE))
        draw.line((0, y, SIZE, y), fill=(r, g, b, 255))

    # Restrained city-light grid, kept abstract to avoid odd generated forms.
    for x in range(80, 760, 80):
        draw.line((x, 120, x, 650), fill=(67, 203, 224, 38), width=1)
    for y in range(160, 660, 70):
        draw.line((70, y, 730, y), fill=(255, 71, 180, 28), width=1)
    draw.line((80, 612, 720, 612), fill=(0, 216, 234, 130), width=3)
    draw.line((80, 633, 720, 633), fill=(255, 62, 181, 120), width=3)
    draw.rectangle((88, 120, 712, 642), outline=(255, 255, 255, 30), width=2)
    draw.rectangle((112, 144, 688, 618), outline=(255, 255, 255, 18), width=1)

    title = font(74, True)
    sub = font(30)
    draw.text((96, 238), "NEON", font=title, fill=(255, 255, 255, 245))
    draw.text((96, 318), "HOURS", font=title, fill=(255, 255, 255, 245))
    draw.text((102, 405), "네온 아워스", font=sub, fill=(130, 239, 247, 220))
    draw.line((102, 462, 452, 462), fill=(255, 62, 181, 170), width=4)
    draw.text((104, 678), "K-URBAN POP  /  NIGHT DRIVE", font=font(24), fill=(255, 255, 255, 190))
    return im


def pansori(vol: int) -> Image.Image:
    warm = vol == 1
    paper = "#f4ecd9" if warm else "#eef1f8"
    tint = "#dfc99e" if warm else "#cbd6ea"
    im = Image.new("RGB", (SIZE, SIZE), paper)
    noise = Image.effect_noise((SIZE, SIZE), 10).convert("L")
    im = Image.composite(Image.new("RGB", (SIZE, SIZE), tint), im, noise)
    draw = ImageDraw.Draw(im, "RGBA")

    accent = (154, 48, 35, 225) if warm else (45, 78, 153, 225)
    ink = (38, 32, 26, 238) if warm else (27, 32, 52, 238)
    muted = (69, 57, 42, 74) if warm else (44, 53, 83, 74)

    margin = 84
    draw.rectangle((margin, margin, SIZE - margin, SIZE - margin), outline=muted, width=2)
    draw.rectangle((margin + 18, margin + 18, SIZE - margin - 18, SIZE - margin - 18), outline=(*muted[:3], 36), width=1)

    # Three quiet story markers, deliberately geometric rather than figurative.
    marker_y = 312
    for i, x in enumerate([220, 400, 580], start=1):
        draw.rectangle((x - 44, marker_y - 44, x + 44, marker_y + 44), outline=(*ink[:3], 78), width=2)
        draw.text((x - 13, marker_y - 23), str(i), font=font(34, True), fill=(*ink[:3], 210))
    draw.line((176, 430, 624, 430), fill=accent, width=5)
    for y in [456, 482, 508]:
        draw.line((176, y, 624, y), fill=(*ink[:3], 44), width=1)

    top = "성서 판소리 제일집" if vol == 1 else "성서 판소리 제이집"
    en = "BIBLE PANSORI VOL.1" if vol == 1 else "BIBLE PANSORI VOL.2"
    text_center(draw, (400, 168), top, font(52, True), ink)
    text_center(draw, (400, 222), "세 이야기", font(29), (*ink[:3], 200))
    text_center(draw, (400, 608), en, font(37, True), ink)
    text_center(draw, (400, 658), "THREE SACRED TALES", font(25), (*ink[:3], 205))
    return im


def main() -> int:
    save(neon_hours(), "neon_hours-네온-아워스", "designed from NEON_HOURS_album.md cover prompt")
    save(pansori(1), "bible-pansori-vol-1-three-sacred-tales", "designed from bible_pansori_vol1_album.md cover prompt")
    save(pansori(2), "bible-pansori-vol-2-three-sacred-tales", "designed from bible_pansori_vol2_album.md cover prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
