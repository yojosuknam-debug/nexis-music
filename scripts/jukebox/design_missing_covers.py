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


# 영상 썸네일이 아직 없어 임시로 그린 표지 — 썸네일이 생기면 sync_project_covers 가 바꾼다
AUTO_REPLACE = {"between-two-midnights-sacred-chant-for-christmas-and-the-new-year"}


def save(im: Image.Image, slug: str, note: str) -> None:
    out = COVERS / f"{slug}.jpg"
    im.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    meta[slug] = {"kind": "designed_cover", "src": note}
    if slug in AUTO_REPLACE:
        meta[slug]["auto_replace"] = True
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


def between_two_midnights() -> Image.Image:
    # image.md: stone abbey cloister at midnight, ivory / deep navy / soft gold,
    # no faces, no direct religious icons or candles.
    im = Image.new("RGB", (SIZE, SIZE), "#0b1426")
    draw = ImageDraw.Draw(im, "RGBA")
    for y in range(SIZE):
        t = y / SIZE
        draw.line((0, y, SIZE, y), fill=(int(10 + 14 * t), int(18 + 18 * t), int(40 + 22 * t), 255))

    # Pale shaft of moonlight falling from the upper left.
    shaft = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shaft).polygon([(150, 0), (300, 0), (560, 800), (330, 800)], fill=46)
    from PIL import ImageFilter as _F
    shaft = shaft.filter(_F.GaussianBlur(40))
    im.paste(Image.new("RGB", (SIZE, SIZE), "#e9e2cf"), (0, 0), shaft)
    draw = ImageDraw.Draw(im, "RGBA")

    # Romanesque cloister: a stone wall with three round arches; the middle one opens onto warm light.
    top, base = 270, 640
    openings = [(112, 268), (322, 478), (532, 688)]
    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse((250, 250, 550, 700), fill=150)
    glow = glow.filter(_F.GaussianBlur(55))
    im.paste(Image.new("RGB", (SIZE, SIZE), "#cfa75e"), (0, 0), glow)

    wall = Image.new("L", (SIZE, SIZE), 0)
    wd = ImageDraw.Draw(wall)
    wd.rectangle((70, top, 730, base), fill=255)
    for x0, x1 in openings:
        r = (x1 - x0) // 2
        wd.rectangle((x0, top + 40 + r, x1, base), fill=0)
        wd.ellipse((x0, top + 40, x1, top + 40 + 2 * r), fill=0)
    stone = Image.new("RGB", (SIZE, SIZE), "#8f8a7c")
    sd = ImageDraw.Draw(stone)
    for y in range(top, base, 28):                      # coursed masonry lines
        sd.line((0, y, SIZE, y), fill="#7c7769", width=2)
    im.paste(stone, (0, 0), wall)
    draw = ImageDraw.Draw(im, "RGBA")
    for x0, x1 in openings:                              # voussoir edge
        r = (x1 - x0) // 2
        draw.arc((x0 - 8, top + 32, x1 + 8, top + 48 + 2 * r), 180, 360, fill=(160, 150, 124, 255), width=8)
    draw.rectangle((62, top - 14, 738, top + 4), fill=(168, 160, 138, 255))
    draw.rectangle((62, base - 16, 738, base), fill=(132, 126, 110, 255))
    # Moonlight brightens the wall where the shaft falls; the edges stay in shadow.
    lit = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(lit).polygon([(150, 0), (300, 0), (560, 800), (330, 800)], fill=70)
    lit = Image.composite(lit.filter(_F.GaussianBlur(40)), Image.new("L", (SIZE, SIZE), 0), wall)
    im.paste(Image.new("RGB", (SIZE, SIZE), "#f1ead6"), (0, 0), lit)
    draw = ImageDraw.Draw(im, "RGBA")

    # Worn flagstones.
    draw.rectangle((0, base, SIZE, SIZE), fill=(24, 32, 52, 255))
    for y in range(base + 24, SIZE, 34):
        draw.line((0, y, SIZE, y), fill=(233, 226, 207, 26), width=1)
    draw.polygon([(330, base), (470, base), (560, SIZE), (300, SIZE)], fill=(233, 226, 207, 22))

    # Light snow.
    import random
    rnd = random.Random(1225)
    for _ in range(140):
        x, y, r = rnd.randrange(SIZE), rnd.randrange(SIZE), rnd.choice([1, 1, 2])
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(245, 242, 232, rnd.randrange(70, 170)))

    # Two midnights — two small gold crescents either side of the title rule.
    gold = (214, 182, 112, 240)
    ivory = (241, 236, 222, 250)
    text_center(draw, (400, 92), "BETWEEN TWO", font(50, True), ivory)
    text_center(draw, (400, 152), "MIDNIGHTS", font(64, True), ivory)
    draw.line((250, 206, 550, 206), fill=gold, width=2)
    for cx in (226, 574):
        draw.ellipse((cx - 9, 197, cx + 9, 215), fill=gold)
        draw.ellipse((cx - 4, 194, cx + 12, 212), fill=(16, 26, 50, 255))
    text_center(draw, (400, 236), "Sacred Chant for Christmas and the New Year", font(22), (233, 226, 207, 215))
    vig = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(vig).ellipse((-160, -120, SIZE + 160, SIZE + 160), fill=255)
    vig = vig.filter(_F.GaussianBlur(90))
    im.paste(Image.new("RGB", (SIZE, SIZE), "#060b17"), (0, 0), Image.eval(vig, lambda v: int((255 - v) * 0.75)))
    draw = ImageDraw.Draw(im, "RGBA")
    text_center(draw, (400, 748), "STILL WATERS", font(20, True), (214, 182, 112, 210))
    return im


DESIGNS = {
    "neon_hours-네온-아워스": (neon_hours, "designed from NEON_HOURS_album.md cover prompt"),
    "bible-pansori-vol-1-three-sacred-tales": (lambda: pansori(1), "designed from bible_pansori_vol1_album.md cover prompt"),
    "bible-pansori-vol-2-three-sacred-tales": (lambda: pansori(2), "designed from bible_pansori_vol2_album.md cover prompt"),
    "between-two-midnights-sacred-chant-for-christmas-and-the-new-year":
        (between_two_midnights, "designed from BETWEEN_TWO_MIDNIGHTS image.md"),
}


def main() -> int:
    # 인자로 슬러그를 주면 그것만 만든다(이미 쓰는 표지를 다시 그리지 않게)
    import sys
    picks = sys.argv[1:] or list(DESIGNS)
    for slug in picks:
        make, note = DESIGNS[slug]
        save(make(), slug, note)
    return 0


def _old_main() -> int:
    save(neon_hours(), "neon_hours-네온-아워스", "designed from NEON_HOURS_album.md cover prompt")
    save(pansori(1), "bible-pansori-vol-1-three-sacred-tales", "designed from bible_pansori_vol1_album.md cover prompt")
    save(pansori(2), "bible-pansori-vol-2-three-sacred-tales", "designed from bible_pansori_vol2_album.md cover prompt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
