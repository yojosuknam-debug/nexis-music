"""유튜브 배너 2560×1440 — 모든 기기에서 보이는 가운데 1546×423 안에 프로필·채널명."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

prof = Image.open("profile-800.png").convert("RGB")
BW, BH = 2560, 1440
ban = Image.new("RGB", (BW, BH), (13, 15, 20))
glow = Image.new("RGB", (BW, BH), (0, 0, 0))
d = ImageDraw.Draw(glow)
d.ellipse((300, 200, 1500, 1200), fill=(70, 120, 108))
d.ellipse((1200, 300, 2300, 1300), fill=(120, 60, 90))
ban = Image.blend(ban, glow.filter(ImageFilter.GaussianBlur(220)), 0.8)
d = ImageDraw.Draw(ban)
F = lambda sz, b=True: ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf" if b else "C:/Windows/Fonts/segoeui.ttf", sz)
cb = 300
cm = Image.new("L", (cb, cb), 0)
ImageDraw.Draw(cm).ellipse((0, 0, cb - 1, cb - 1), fill=255)
t1, t2 = "yojosuknam Radio", "LIVE 24/7  ·  original albums, non-stop"
f1, f2 = F(112), F(54, False)
block = cb + 56 + max(d.textlength(t1, font=f1), 52 + d.textlength(t2, font=f2))
x0 = int((BW - block) / 2)
ban.paste(prof.resize((cb, cb), Image.LANCZOS), (x0, BH // 2 - cb // 2), cm)
x = x0 + cb + 56
d.text((x, BH // 2 - 138), t1, font=f1, fill=(255, 255, 255))
d.ellipse((x, BH // 2 + 34, x + 30, BH // 2 + 64), fill=(255, 77, 94))
d.text((x + 48, BH // 2 + 16), t2, font=f2, fill=(225, 232, 230))
ban.save("banner-2560x1440.jpg", quality=92)
print("block", int(block), "/ safe 1546")
