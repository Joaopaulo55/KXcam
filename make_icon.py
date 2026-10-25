# Gera o MESMO ícone para PC (icon.ico/png) e Android (mipmaps)
import os
from PIL import Image, ImageDraw, ImageFont
S = 1024
g = Image.new("RGB", (S, S)); gd = ImageDraw.Draw(g)
for y in range(S): gd.line([(0, y), (S, y)], fill=(int(10 + 20*y/S), int(20 + 60*y/S), int(60 + 120*y/S)))
m = Image.new("L", (S, S), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, S-1, S-1], radius=230, fill=255)
im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); im.paste(g, (0, 0), m)
d = ImageDraw.Draw(im); cx, cy = S//2, S//2 - 70
for r, c in [(330, (255, 255, 255, 255)), (290, (15, 23, 42, 255)), (215, (34, 211, 238, 255)), (165, (8, 12, 28, 255)), (70, (255, 255, 255, 210))]:
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=c)
try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", 210)
except Exception:
    try: font = ImageFont.truetype("arialbd.ttf", 210)
    except Exception: font = ImageFont.load_default()
d.text((S//2, S - 140), "KX", font=font, fill="white", anchor="mm")
here = os.path.dirname(os.path.abspath(__file__))
im.save(os.path.join(here, "pc", "icon.png"))
im.save(os.path.join(here, "pc", "icon.ico"), sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
for n, sz in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    p = os.path.join(here, "android/app/src/main/res", f"mipmap-{n}"); os.makedirs(p, exist_ok=True)
    im.resize((sz, sz), Image.LANCZOS).save(os.path.join(p, "ic_launcher.png"))
