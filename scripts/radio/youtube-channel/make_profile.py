"""유튜브 프로필: 곰(사용자 연필 그림)이 레트로 라디오 뒤에서 얼굴을 내민 모습. 800×800, 원형으로 잘림."""
import random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

random.seed(3)
W = 800
INK = (55, 55, 55)


def pencil_line(d, pts, width=5, passes=3, jitter=2.2, col=INK):
    """연필처럼 여러 번 겹쳐 긋기(조금씩 흔들림)."""
    for _ in range(passes):
        q = [(x + random.uniform(-jitter, jitter), y + random.uniform(-jitter, jitter)) for x, y in pts]
        d.line(q, fill=col + (random.randint(140, 220),), width=width, joint="curve")


def rrect_pts(x0, y0, x1, y1, r, n=10):
    import math
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    return pts


def circle_pts(cx, cy, r, n=48):
    import math
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def paper_texture(img):
    """종이 결 — 아주 옅은 잡티."""
    noise = Image.effect_noise(img.size, 18).convert("L").point(lambda v: 255 - (255 - v) // 9)
    return ImageChops.multiply(img, Image.merge("RGB", [noise] * 3))


canvas = Image.new("RGB", (W, W), (255, 255, 255))

# 1) 곰: 연필 그림에서 곰만 오려 위쪽에 배치(아래 잘린 턱은 라디오가 가린다)
src = Image.open("D:/YH/APP/nexis-music/public/radio/icon-1024.png").convert("RGB")
g = src.convert("L").point(lambda v: 255 if v < 200 else 0)
l, t, r, b = g.getbbox()
bear = src.crop((l, t, r, b))
bw = 560
bear = bear.resize((bw, int(bear.height * bw / bear.width)), Image.LANCZOS)
bx, by = (W - bw) // 2, 92
canvas.paste(bear, (bx, by))
bear_bottom = by + bear.height

# 2) 라디오(앞): 흰 몸통으로 곰 아래를 덮고 연필 선으로 그린다
layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(layer)
rx0, rx1 = 150, 650
ry0, ry1 = bear_bottom - 48, bear_bottom - 48 + 250
body = Image.new("L", (W, W), 0)
ImageDraw.Draw(body).rounded_rectangle((rx0, ry0, rx1, ry1), radius=44, fill=255)
canvas.paste((250, 248, 244), (0, 0), body)                # 몸통 바탕(살짝 따뜻한 흰색)
# 안테나 — 라디오 위 오른쪽에서 곰 귀 옆으로
pencil_line(d, [(rx1 - 90, ry0 + 4), (rx1 + 40, ry0 - 190)], width=5)
d.ellipse((rx1 + 30, ry0 - 202, rx1 + 52, ry0 - 180), outline=INK + (210,), width=5)
# 몸통 테두리·손잡이 느낌의 윗선
pencil_line(d, rrect_pts(rx0, ry0, rx1, ry1, 44), width=6)
pencil_line(d, [(rx0 + 30, ry0 + 26), (rx1 - 30, ry0 + 26)], width=3, passes=2)
# 스피커(왼쪽 원 + 빗금)
scx, scy, sr = rx0 + 125, (ry0 + ry1) // 2 + 14, 78
pencil_line(d, circle_pts(scx, scy, sr), width=5)
for k in range(-4, 5):
    y = scy + k * 16
    half = (sr * sr - (k * 16) ** 2) ** 0.5 - 10
    if half > 8:
        pencil_line(d, [(scx - half, y), (scx + half, y)], width=3, passes=2, jitter=1.4)
# 다이얼 창(오른쪽 위) + 눈금 + 바늘
wx0, wy0, wx1, wy1 = rx0 + 245, ry0 + 58, rx1 - 40, ry0 + 128
pencil_line(d, rrect_pts(wx0, wy0, wx1, wy1, 14), width=4)
for i in range(9):
    x = wx0 + 18 + i * (wx1 - wx0 - 36) / 8
    pencil_line(d, [(x, wy1 - 14), (x, wy1 - (30 if i % 2 == 0 else 22))], width=2, passes=1, jitter=0.8)
pencil_line(d, [(wx0 + 120, wy0 + 10), (wx0 + 112, wy1 - 8)], width=4, col=(210, 70, 80))   # 빨간 바늘
# 손잡이 두 개
for cx in (wx0 + 40, wx1 - 40):
    cy = ry1 - 58
    pencil_line(d, circle_pts(cx, cy, 24, 32), width=4)
    pencil_line(d, [(cx, cy - 12), (cx, cy - 2)], width=3, passes=1)
# ON AIR 불빛
d.ellipse((wx0 + 88, ry1 - 68, wx0 + 108, ry1 - 48), fill=(255, 77, 94, 230))

layer = layer.filter(ImageFilter.GaussianBlur(0.6))
canvas.paste(layer, (0, 0), layer)
canvas = paper_texture(canvas)
canvas.save("profile-800.png")

# 미리보기(원형·작은 크기)
m = Image.new("L", (W, W), 0)
ImageDraw.Draw(m).ellipse((0, 0, W - 1, W - 1), fill=255)
prev = Image.new("RGB", (W, W), (24, 24, 24))
prev.paste(canvas, (0, 0), m)
sheet = Image.new("RGB", (900, 420), (40, 44, 52))
sheet.paste(prev.resize((380, 380)), (20, 20))
x = 430
for n in (176, 88, 48, 32):
    sheet.paste(prev.resize((n, n)), (x, 210 - n // 2))
    x += n + 24
sheet.save("C:/Users/YOJOSU~1/AppData/Local/Temp/claude/d--YH-APP-nexis-lab-home/b205865a-387a-4f72-b1e2-318e808ed01b/scratchpad/profile_preview.png")
print("ok", bear_bottom, ry0, ry1)
