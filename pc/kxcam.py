"""KX Cam PC v2 - by João Francisco Vica Paulo
Recebe vídeo+áudio do telemóvel (USB via ADB ou Wi-Fi), controla a câmara, grava e cria câmara virtual."""
import os, sys, json, time, wave, tempfile, subprocess, threading, http.client, urllib.request
import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np, cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import deps

PORT = 4747
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.expanduser("~"), "Videos", "KXCam")
TMP = os.path.join(os.environ.get("PUBLIC", tempfile.gettempdir()), "KXCam_tmp")   # caminho ASCII p/ OpenCV
CFG = os.path.join(deps.HOME, "config.json")
ACC, BG, PANEL, RED = "#22d3ee", "#0b1220", "#111a2e", "#dc2626"

def safe(fn):
    try: return fn()
    except Exception: return None

def load_cfg():
    try: return json.load(open(CFG, encoding="utf-8"))
    except Exception: return {}

# ---------------------------------------------------------------- rede
class Client:
    def __init__(s, on_frame):
        s.on_frame = on_frame; s.host = None; s.run = False; s.rec_audio = None
        s.mute = False; s.gain = 1.0; s.out_dev = None; s.bytes = 0; s.connected = False
    def start(s, host):
        s.host = host; s.run = True; s.connected = False
        threading.Thread(target=s._video, daemon=True).start()
        threading.Thread(target=s._audio, daemon=True).start()
    def stop(s): s.run = False; s.connected = False
    def cmd(s, **kw):
        if not s.host: return
        url = f"http://{s.host}:{PORT}/cmd?" + "&".join(f"{k}={v}" for k, v in kw.items())
        threading.Thread(target=lambda: safe(lambda: urllib.request.urlopen(url, timeout=3).read()), daemon=True).start()
    def _video(s):
        while s.run:
            try:
                conn = http.client.HTTPConnection(s.host, PORT, timeout=8); conn.request("GET", "/video"); r = conn.getresponse()
                while s.run:
                    line = r.readline()
                    if not line: break
                    if not line.startswith(b"--kx"): continue
                    ln = rot = 0
                    while True:
                        h = r.readline().strip()
                        if not h: break
                        k, _, v = h.partition(b":"); k = k.lower()
                        if k == b"content-length": ln = int(v)
                        elif k == b"x-rot": rot = int(v)
                    data = r.read(ln); r.read(2); s.bytes += ln
                    f = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                    if f is None: continue
                    if rot: f = cv2.rotate(f, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[rot])
                    s.connected = True; s.on_frame(f)
            except Exception:
                s.connected = False; time.sleep(1)
    def _audio(s):
        try: import sounddevice as sd
        except Exception: return
        def mk(dev):
            o = sd.RawOutputStream(samplerate=16000, channels=1, dtype="int16", device=dev); o.start(); return o
        while s.run:
            try:
                conn = http.client.HTTPConnection(s.host, PORT, timeout=8); conn.request("GET", "/audio"); r = conn.getresponse()
                cur = s.out_dev; out = mk(cur)
                while s.run:
                    d = r.read(3200)
                    if not d: break
                    d = d[:len(d) // 2 * 2]
                    if s.gain != 1.0: d = np.clip(np.frombuffer(d, np.int16).astype(np.float32) * s.gain, -32768, 32767).astype(np.int16).tobytes()
                    w = s.rec_audio
                    if w: safe(lambda: w.writeframes(d))
                    if cur != s.out_dev: out.close(); cur = s.out_dev; out = mk(cur)
                    if not s.mute: out.write(d)
                out.close()
            except Exception: time.sleep(1)

# ---------------------------------------------------------------- gravação
class ScreenGrab:
    sct = None
    def __call__(s):
        import mss
        if s.sct is None: s.sct = mss.mss()
        return np.ascontiguousarray(np.array(s.sct.grab(s.sct.monitors[1]))[:, :, :3])

class Rec(threading.Thread):
    def __init__(s, grab, path, fps):
        super().__init__(daemon=True); s.grab, s.path, s.fps, s.on = grab, path, fps, True
    def run(s):
        w = None; t0 = time.time(); n = 0
        while s.on:
            f = s.grab()
            if f is not None:
                if w is None:
                    s.size = (f.shape[1], f.shape[0]); w = cv2.VideoWriter(s.path, cv2.VideoWriter_fourcc(*"mp4v"), s.fps, s.size)
                if (f.shape[1], f.shape[0]) != s.size: f = cv2.resize(f, s.size)
                tgt = int((time.time() - t0) * s.fps)
                while n <= tgt: w.write(f); n += 1
            time.sleep(0.004)
        if w: w.release()

def finalize(vtmp, atmp, final):
    ok = False
    try:
        import imageio_ffmpeg
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", vtmp] + (["-i", atmp] if atmp else []) + \
              ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"] + \
              (["-c:a", "aac", "-shortest"] if atmp else []) + [final]
        subprocess.run(cmd, capture_output=True, creationflags=deps.NOWIN); ok = os.path.exists(final)
    except Exception: pass
    if not ok and os.path.exists(vtmp): safe(lambda: shutil_move(vtmp, final))
    for p in (vtmp, atmp):
        if p and os.path.exists(p): safe(lambda: os.remove(p))

def shutil_move(a, b):
    import shutil; shutil.move(a, b)

FILTERS = ["Normal", "P&B", "Sépia", "Nítido", "Quente", "Frio"]
def apply_filter(f, name):
    if name == "P&B": return cv2.cvtColor(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    if name == "Sépia": return cv2.transform(f, np.array([[0.131, 0.534, 0.272], [0.168, 0.686, 0.349], [0.189, 0.769, 0.393]]))
    if name == "Nítido": return cv2.addWeighted(f, 1.6, cv2.GaussianBlur(f, (0, 0), 3), -0.6, 0)
    if name == "Quente": return cv2.multiply(f, (0.88, 1.0, 1.15, 0))
    if name == "Frio": return cv2.multiply(f, (1.15, 1.0, 0.88, 0))
    return f

# ---------------------------------------------------------------- app
class App:
    def __init__(s):
        s.cfg = load_cfg()
        ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
        r = s.root = ctk.CTk(); r.title("KX Cam"); r.geometry("1260x780"); r.minsize(1040, 660); r.configure(fg_color=BG)
        r.after(250, lambda: safe(lambda: r.iconbitmap(os.path.join(BASE, "icon.ico"))))
        s.front = False; s.rot = 0; s.mirror = s.vflip = False; s.automirror = True; s.bri = 0; s.con = 1.0
        s.filter = "Normal"; s.grid = False; s.vcam = None; s.rec = None; s.srec = None; s.last = None
        s.fseq = s.seen = s.fcount = s.fps = 0; s.pushed = False; s.t0 = time.time(); s.b0 = 0; s.kbps = 0
        s.res, s.fpsv, s.q = s.cfg.get("res", "720p"), s.cfg.get("fps", "30"), int(s.cfg.get("q", 75))
        s.zoom = 0; s.deb = {}; s.full = False; s.vc_on = False
        s.c = Client(s.on_frame)
        r.grid_columnconfigure(0, weight=1); r.grid_rowconfigure(0, weight=1)
        # ----- área principal
        main = ctk.CTkFrame(r, fg_color=BG, corner_radius=0); main.grid(row=0, column=0, sticky="nsew", padx=(14, 6), pady=14)
        main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=1)
        s.view = tk.Label(main, bg="#05080f", fg=ACC, font=("Segoe UI", 17), text="KX Cam\nLigue o telemóvel e clique em CONECTAR\n\nby João Francisco Vica Paulo")
        s.view.grid(row=0, column=0, sticky="nsew")
        s.view.bind("<MouseWheel>", s.on_wheel); s.view.bind("<Double-Button-1>", lambda e: s.toggle_full())
        bar = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12); bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        s.brec = ctk.CTkButton(bar, text="● Gravar câmara", width=140, fg_color="#1e293b", hover_color=RED, command=s.toggle_rec)
        s.bsrec = ctk.CTkButton(bar, text="▣ Gravar ecrã", width=130, fg_color="#1e293b", hover_color=RED, command=s.toggle_screen)
        for b in (s.brec, s.bsrec, ctk.CTkButton(bar, text="◉ Foto", width=90, fg_color="#1e293b", command=s.snapshot),
                  ctk.CTkButton(bar, text="⛶ Ecrã inteiro", width=120, fg_color="#1e293b", command=s.toggle_full)):
            b.pack(side="left", padx=6, pady=8)
        s.top = ctk.CTkSwitch(bar, text="Sempre no topo", command=lambda: r.attributes("-topmost", s.top.get())); s.top.pack(side="left", padx=12)
        s.stat = ctk.CTkLabel(bar, text="—", text_color=ACC, font=("Segoe UI", 12, "bold")); s.stat.pack(side="right", padx=14)
        # ----- painel lateral
        side = s.side = ctk.CTkFrame(r, fg_color=PANEL, corner_radius=16, width=380); side.grid(row=0, column=1, sticky="ns", padx=(6, 14), pady=14)
        side.grid_propagate(False); side.pack_propagate(False)
        hd = ctk.CTkFrame(side, fg_color="transparent"); hd.pack(fill="x", padx=14, pady=(14, 6))
        safe(lambda: ctk.CTkLabel(hd, text="", image=ctk.CTkImage(Image.open(os.path.join(BASE, "icon.png")), size=(50, 50))).pack(side="left"))
        t = ctk.CTkFrame(hd, fg_color="transparent"); t.pack(side="left", padx=10)
        ctk.CTkLabel(t, text="KX Cam", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ctk.CTkLabel(t, text="by João Francisco Vica Paulo", text_color=ACC, font=("Segoe UI", 11)).pack(anchor="w")
        s.mode = ctk.CTkSegmentedButton(side, values=["USB", "Wi-Fi"]); s.mode.set(s.cfg.get("mode", "USB")); s.mode.pack(fill="x", padx=14, pady=(8, 4))
        s.ip = ctk.CTkEntry(side, placeholder_text="IP do telemóvel (modo Wi-Fi)"); s.ip.insert(0, s.cfg.get("ip", "")); s.ip.pack(fill="x", padx=14, pady=4)
        s.bconn = ctk.CTkButton(side, text="CONECTAR", height=42, font=("Segoe UI", 14, "bold"), command=s.connect); s.bconn.pack(fill="x", padx=14, pady=6)
        s.status = ctk.CTkLabel(side, text="● Desligado", text_color="#94a3b8"); s.status.pack(pady=(0, 6))
        tabs = ctk.CTkTabview(side, fg_color="#0e1627", height=420); tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for n in ("Câmara", "Imagem", "Áudio", "Extras"): tabs.add(n)
        # Câmara
        p = tabs.tab("Câmara")
        ctk.CTkButton(p, text="⟲ Trocar câmara (frontal/traseira)", command=s.swap).pack(fill="x", pady=4)
        s.sw(p, "Flash / lanterna", lambda v: s.c.cmd(torch=int(v)))
        s.opt(p, "Resolução", ["360p", "480p", "720p", "1080p"], s.res, s.set_res)
        s.opt(p, "FPS alvo", ["15", "24", "30", "60"], s.fpsv, s.set_fps)
        s.sl(p, "Qualidade JPEG (menor = mais FPS)", 30, 100, s.q, s.set_q)
        s.zs = s.sl(p, "Zoom", 0, 100, 0, lambda v: (setattr(s, "zoom", v), s.c.cmd(zoom=round(v / 100, 2))))
        s.sl(p, "Exposição", -100, 100, 0, lambda v: s.c.cmd(ev=round(v / 100, 2)))
        ctk.CTkButton(p, text="◎ Focar ao centro", fg_color="#1e293b", command=lambda: s.c.cmd(focus=1)).pack(fill="x", pady=8)
        # Imagem
        p = tabs.tab("Imagem")
        s.sw(p, "Espelhar", lambda v: setattr(s, "mirror", v))
        s.sw(p, "Espelhar auto na câmara frontal", lambda v: setattr(s, "automirror", v), True)
        s.sw(p, "Inverter (vertical)", lambda v: setattr(s, "vflip", v))
        ctk.CTkButton(p, text="↻ Rodar 90°", fg_color="#1e293b", command=lambda: setattr(s, "rot", (s.rot + 90) % 360)).pack(fill="x", pady=4)
        s.opt(p, "Filtro", FILTERS, "Normal", lambda v: setattr(s, "filter", v))
        s.sl(p, "Brilho", -100, 100, 0, lambda v: setattr(s, "bri", v), live=True)
        s.sl(p, "Contraste", 50, 200, 100, lambda v: setattr(s, "con", v / 100), live=True)
        s.sw(p, "Grelha (só pré-visualização)", lambda v: setattr(s, "grid", v))
        # Áudio
        p = tabs.tab("Áudio")
        s.sw(p, "Silenciar no PC", lambda v: setattr(s.c, "mute", v))
        s.sl(p, "Volume do microfone (%)", 0, 300, 100, lambda v: setattr(s.c, "gain", v / 100), live=True)
        devs = ["Predefinido"]
        safe(lambda: devs.extend(f"{i} - {d['name']}" for i, d in enumerate(__import__("sounddevice").query_devices()) if d["max_output_channels"] > 0))
        s.opt(p, "Saída de áudio", devs, "Predefinido", lambda v: setattr(s.c, "out_dev", None if v == "Predefinido" else int(v.split(" - ")[0])))
        ctk.CTkLabel(p, text="Dica: escolha 'CABLE Input' (VB-Cable) para usar o\nmicrofone do telemóvel no Discord/Zoom.", text_color="#94a3b8", justify="left").pack(pady=10)
        # Extras
        p = tabs.tab("Extras")
        s.sw(p, "Câmara virtual (OBS Virtual Camera)", s.toggle_vcam)
        ctk.CTkButton(p, text="Instalar app no telemóvel (USB)", command=s.install_apk).pack(fill="x", pady=6)
        ctk.CTkButton(p, text="Abrir pasta das gravações", fg_color="#1e293b", command=lambda: (os.makedirs(OUT, exist_ok=True), os.startfile(OUT))).pack(fill="x", pady=4)
        ctk.CTkLabel(p, text="Atalhos: Ctrl+R gravar • Ctrl+S foto • F11 ecrã inteiro\nRoda do rato na imagem = zoom • Duplo clique = ecrã inteiro\nNo browser: http://IP:4747/video", text_color="#94a3b8", justify="left").pack(pady=12)
        r.bind("<Control-r>", lambda e: s.toggle_rec()); r.bind("<Control-s>", lambda e: s.snapshot())
        r.bind("<F11>", lambda e: s.toggle_full()); r.bind("<Escape>", lambda e: s.full and s.toggle_full())
        r.protocol("WM_DELETE_WINDOW", s.close)
        threading.Thread(target=lambda: safe(deps.ensure_adb), daemon=True).start()
        s.tick(); r.mainloop()

    # ---------- helpers de UI
    def sw(s, p, txt, cb, init=False):
        v = ctk.BooleanVar(value=init); w = ctk.CTkSwitch(p, text=txt, variable=v, command=lambda: cb(v.get())); w.pack(anchor="w", pady=5)
        if init: cb(True)
        return w
    def opt(s, p, txt, vals, init, cb):
        ctk.CTkLabel(p, text=txt).pack(anchor="w", pady=(8, 0)); m = ctk.CTkOptionMenu(p, values=vals, command=cb); m.set(init); m.pack(fill="x"); return m
    def sl(s, p, txt, lo, hi, init, cb, live=False):
        lab = ctk.CTkLabel(p, text=f"{txt}: {int(init)}"); lab.pack(anchor="w", pady=(8, 0))
        key = txt
        def on(v):
            lab.configure(text=f"{txt}: {int(v)}")
            if live: cb(v); return
            if key in s.deb: s.root.after_cancel(s.deb[key])
            s.deb[key] = s.root.after(150, lambda: cb(v))      # envia ao parar de mexer
        w = ctk.CTkSlider(p, from_=lo, to=hi, command=on); w.set(init); w.pack(fill="x"); return w
    def st(s, t, c="#94a3b8"): s.root.after(0, lambda: s.status.configure(text=t, text_color=c))

    # ---------- definições da câmara
    def set_res(s, v): s.res = v; s.c.cmd(res=v[:-1])
    def set_fps(s, v): s.fpsv = v; s.c.cmd(fps=v)
    def set_q(s, v): s.q = int(v); s.c.cmd(q=int(v))
    def swap(s): s.front = not s.front; s.c.cmd(cam="front" if s.front else "back")
    def push_settings(s):
        s.c.cmd(res=s.res[:-1], fps=s.fpsv, q=s.q, cam="front" if s.front else "back")
    def on_wheel(s, e):
        s.zoom = max(0, min(100, s.zoom + (5 if e.delta > 0 else -5))); s.zs.set(s.zoom); s.c.cmd(zoom=round(s.zoom / 100, 2))

    # ---------- ligação
    def connect(s):
        if s.c.run:
            s.c.stop(); s.bconn.configure(text="CONECTAR", fg_color=["#3B8ED0", "#1F6AA5"]); s.st("● Desligado"); return
        s.cfg.update(mode=s.mode.get(), ip=s.ip.get(), res=s.res, fps=s.fpsv, q=s.q)
        safe(lambda: (os.makedirs(deps.HOME, exist_ok=True), json.dump(s.cfg, open(CFG, "w", encoding="utf-8"))))
        s.bconn.configure(text="DESLIGAR", fg_color=RED); s.pushed = False
        threading.Thread(target=s._connect, daemon=True).start()
    def _connect(s):
        try:
            if s.mode.get() == "USB":
                s.st("A preparar ADB (1ª vez descarrega)...", ACC)
                out = deps.adb("devices").stdout
                if not [l for l in out.splitlines()[1:] if l.strip().endswith("device")]:
                    raise RuntimeError("Nenhum telemóvel detetado.\nLigue o cabo, ative a Depuração USB e aceite o pedido no telemóvel.")
                deps.adb("forward", f"tcp:{PORT}", f"tcp:{PORT}")
                deps.adb("shell", "am", "start", "-n", "com.kx.cam/.MainActivity", "--ez", "autostart", "true")
                host = "127.0.0.1"
            else:
                host = s.ip.get().strip()
                if not host: raise RuntimeError("Escreva o IP que aparece no app do telemóvel.")
            s.c.start(host); s.st("A ligar a " + host + " ...", ACC)
        except Exception as e:
            s.root.after(0, lambda: (messagebox.showerror("KX Cam", str(e)), s.bconn.configure(text="CONECTAR", fg_color=["#3B8ED0", "#1F6AA5"]), s.st("● Desligado")))
    def install_apk(s):
        def go():
            apk = next((p for p in (os.path.join(BASE, "kxcam.apk"), os.path.join(os.path.dirname(sys.executable), "kxcam.apk")) if os.path.exists(p)), None)
            if not apk: apk = filedialog.askopenfilename(title="Escolha o APK do KX Cam", filetypes=[("APK", "*.apk")])
            if not apk: return
            s.st("A instalar APK...", ACC); r = deps.adb("install", "-r", apk)
            s.root.after(0, lambda: messagebox.showinfo("KX Cam", (r.stdout + r.stderr).strip() or "Concluído"))
        threading.Thread(target=go, daemon=True).start()

    # ---------- processamento (thread de rede)
    def on_frame(s, f):
        try:
            if s.mirror ^ (s.front and s.automirror): f = cv2.flip(f, 1)
            if s.vflip: f = cv2.flip(f, 0)
            if s.rot: f = cv2.rotate(f, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[s.rot])
            if s.filter != "Normal": f = apply_filter(f, s.filter)
            if s.bri or s.con != 1.0: f = cv2.convertScaleAbs(f, alpha=s.con, beta=s.bri)
            s.last = f; s.fseq += 1; s.fcount += 1
            if s.vc_on: s.send_vcam(f)
            if not s.pushed: s.pushed = True; s.root.after(0, s.push_settings)
        except Exception: pass
    def toggle_vcam(s, v):
        if v and not deps.ensure_obs(): s.vc_on = False; return
        s.vc_on = v
        if not v and s.vcam: s.vcam.close(); s.vcam = None
    def send_vcam(s, f):
        try:
            import pyvirtualcam
            h, w = f.shape[:2]
            if s.vcam is None or (s.vcam.width, s.vcam.height) != (w, h):
                if s.vcam: s.vcam.close()
                s.vcam = pyvirtualcam.Camera(w, h, 30, fmt=pyvirtualcam.PixelFormat.BGR)
            s.vcam.send(f)
        except Exception as e:
            s.vc_on = False; s.vcam = None; s.root.after(0, lambda: messagebox.showerror("KX Cam", f"Câmara virtual indisponível:\n{e}"))

    # ---------- ecrã
    def tick(s):
        f = s.last
        if f is not None and s.fseq != s.seen:
            s.seen = s.fseq
            h, w = f.shape[:2]; cw, ch = max(s.view.winfo_width(), 2), max(s.view.winfo_height(), 2)
            sc = min(cw / w, ch / h); img = cv2.resize(f, (max(int(w * sc), 1), max(int(h * sc), 1)), interpolation=cv2.INTER_LINEAR)
            if s.grid:
                H, W = img.shape[:2]
                for i in (1, 2):
                    cv2.line(img, (W * i // 3, 0), (W * i // 3, H), (255, 255, 255), 1); cv2.line(img, (0, H * i // 3), (W, H * i // 3), (255, 255, 255), 1)
            ph = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            s.view.configure(image=ph, text=""); s.view.image = ph
        if time.time() - s.t0 >= 1:
            dt = time.time() - s.t0; s.fps = round(s.fcount / dt); s.fcount = 0
            s.kbps = int((s.c.bytes - s.b0) / 1024 / dt); s.b0 = s.c.bytes; s.t0 = time.time()
            if s.c.run:
                if s.c.connected and s.last is not None:
                    s.status.configure(text=f"● Ligado  {s.last.shape[1]}x{s.last.shape[0]}", text_color="#4ade80")
                    s.stat.configure(text=f"{s.fps} FPS   {s.kbps} KB/s" + ("   ● REC" if s.rec else ""))
                else: s.status.configure(text="● A aguardar vídeo do telemóvel...", text_color=ACC)
        s.root.after(8, s.tick)

    def toggle_full(s):
        s.full = not s.full; s.root.attributes("-fullscreen", s.full)
        s.side.grid_remove() if s.full else s.side.grid()

    # ---------- gravação / foto
    def snapshot(s):
        if s.last is None: return
        os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, f"Foto_{time.strftime('%Y%m%d_%H%M%S')}.png")
        ok, buf = cv2.imencode(".png", s.last)
        if ok: open(p, "wb").write(buf.tobytes()); s.stat.configure(text="Foto guardada ✔")
    def toggle_rec(s):
        if s.rec is None:
            if s.last is None: return messagebox.showwarning("KX Cam", "Ligue a câmara primeiro.")
            os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True); ts = time.strftime("%Y%m%d_%H%M%S")
            s.rv, s.ra, s.rf = os.path.join(TMP, f"{ts}.mp4"), os.path.join(TMP, f"{ts}.wav"), os.path.join(OUT, f"Camera_{ts}.mp4")
            wf = wave.open(s.ra, "wb"); wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); s.rwf = wf; s.c.rec_audio = wf
            s.rec = Rec(lambda: s.last, s.rv, 30); s.rec.start(); s.brec.configure(text="■ Parar gravação", fg_color=RED)
        else:
            s.c.rec_audio = None; s.rec.on = False; s.rec.join(); s.rwf.close()
            threading.Thread(target=finalize, args=(s.rv, s.ra, s.rf), daemon=True).start()
            s.rec = None; s.brec.configure(text="● Gravar câmara", fg_color="#1e293b"); messagebox.showinfo("KX Cam", "Gravação guardada em:\n" + s.rf)
    def toggle_screen(s):
        if s.srec is None:
            os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True); ts = time.strftime("%Y%m%d_%H%M%S")
            s.sv, s.sf = os.path.join(TMP, f"{ts}s.mp4"), os.path.join(OUT, f"Ecra_{ts}.mp4")
            s.srec = Rec(ScreenGrab(), s.sv, 20); s.srec.start(); s.bsrec.configure(text="■ Parar ecrã", fg_color=RED)
        else:
            s.srec.on = False; s.srec.join()
            threading.Thread(target=finalize, args=(s.sv, None, s.sf), daemon=True).start()
            s.srec = None; s.bsrec.configure(text="▣ Gravar ecrã", fg_color="#1e293b"); messagebox.showinfo("KX Cam", "Gravação guardada em:\n" + s.sf)
    def close(s):
        for r in (s.rec, s.srec):
            if r: r.on = False
        s.c.stop(); safe(lambda: s.vcam.close()); s.root.destroy()

if __name__ == "__main__":
    App()
