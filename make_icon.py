# Gera o MESMO ícone (v2) para PC (icon.ico/png) e Android (mipmaps)
import os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S = 2048; K = S / 1024  # super-amostragem
def L(c1, c2, t): return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
# fundo: gradiente diagonal indigo -> violeta -> ciano
bg = Image.new("RGB", (S, S)); px = bg.load()
stops = [(0.0, (9, 12, 38)), (0.55, (52, 38, 190)), (1.0, (6, 182, 212))]
for y in range(S):
    for x in range(0, S):
        t = (x * 0.35 + y * 0.65) / S
        a, b = (stops[0], stops[1]) if t < stops[1][0] else (stops[1], stops[2])
        u = max(0, min(1, (t - a[0]) / (b[0] - a[0]))); px[x, y] = L(a[1], b[1], u)
mask = Image.new("L", (S, S), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, S-1, S-1], radius=int(235*K), fill=255)
im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); im.paste(bg, (0, 0), mask)
cx, cy, R = S//2, int(445*K), int(300*K)
# sombra da lente
sh = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([cx-R, cy-R+int(30*K), cx+R, cy+R+int(30*K)], fill=(0, 0, 20, 170))
im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(int(26*K))))
d = ImageDraw.Draw(im)
def disc(r, c1, c2):  # disco com gradiente radial
    steps = 60
    for i in range(steps):
        rr = int(r * (1 - i / steps)); d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], fill=L(c1, c2, i / steps) + (255,))
disc(R, (235, 240, 250), (120, 130, 155))            # aro metálico
disc(int(R*0.88), (28, 32, 52), (8, 10, 22))          # corpo da lente
disc(int(R*0.70), (30, 60, 120), (4, 8, 28))          # vidro externo
disc(int(R*0.52), (34, 211, 238), (20, 40, 150))      # vidro colorido
disc(int(R*0.26), (10, 14, 40), (2, 4, 14))           # pupila
# reflexos
hl = Image.new("RGBA", (S, S), (0, 0, 0, 0)); h = ImageDraw.Draw(hl)
h.ellipse([cx-int(R*0.45), cy-int(R*0.50), cx-int(R*0.05), cy-int(R*0.18)], fill=(255, 255, 255, 190))
h.ellipse([cx+int(R*0.12), cy+int(R*0.10), cx+int(R*0.30), cy+int(R*0.26)], fill=(255, 255, 255, 110))
im = Image.alpha_composite(im, hl.filter(ImageFilter.GaussianBlur(int(7*K))))
d = ImageDraw.Draw(im)
# ponto REC
rx, ry, rr = int(800*K), int(205*K), int(44*K)
glow = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(glow).ellipse([rx-rr*2, ry-rr*2, rx+rr*2, ry+rr*2], fill=(255, 40, 60, 140))
im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(int(22*K)))); d = ImageDraw.Draw(im)
d.ellipse([rx-rr, ry-rr, rx+rr, ry+rr], fill=(255, 59, 80, 255)); d.ellipse([rx-rr//3-int(8*K), ry-rr//2, rx-int(2*K), ry-int(4*K)], fill=(255, 255, 255, 170))
# texto KX
font = None
for f in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
    try: font = ImageFont.truetype(f, int(235*K)); break
    except Exception: pass
font = font or ImageFont.load_default()
tx, ty = S//2, int(858*K)
d.text((tx+int(5*K), ty+int(8*K)), "KX", font=font, fill=(0, 0, 30, 140), anchor="mm")
d.text((tx, ty), "KX", font=font, fill="white", anchor="mm")
im = im.resize((1024, 1024), Image.LANCZOS)
here = os.path.dirname(os.path.abspath(__file__))
im.save(os.path.join(here, "pc", "icon.png"))
im.save(os.path.join(here, "pc", "icon.ico"), sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
for n, sz in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    p = os.path.join(here, "android/app/src/main/res", f"mipmap-{n}"); os.makedirs(p, exist_ok=True)
    im.resize((sz, sz), Image.LANCZOS).save(os.path.join(p, "ic_launcher.png"))
