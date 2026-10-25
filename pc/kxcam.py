"""KX Cam PC - by João Francisco Vica Paulo
Recebe vídeo+áudio do telemóvel (USB via ADB ou Wi-Fi), controla a câmara, grava e cria câmara virtual."""
import os, sys, time, wave, subprocess, threading, urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np, cv2
from PIL import Image, ImageTk
import deps

PORT = 4747
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.expanduser("~"), "Videos", "KXCam")
BG, FG, AC = "#0b1220", "#e2e8f0", "#22d3ee"

class Client:
    def __init__(s):
        s.host = None; s.run = False; s.frame = None; s.seq = 0; s.rec_audio = None
        s.mute = False; s.out_dev = None; s.err = ""
    def start(s, host):
        s.host = host; s.run = True; s.frame = None
        threading.Thread(target=s._video, daemon=True).start()
        threading.Thread(target=s._audio, daemon=True).start()
    def stop(s): s.run = False
    def cmd(s, **kw):
        if not s.host: return
        url = f"http://{s.host}:{PORT}/cmd?" + "&".join(f"{k}={v}" for k, v in kw.items())
        def go():
            try: urllib.request.urlopen(url, timeout=3).read()
            except Exception: pass
        threading.Thread(target=go, daemon=True).start()
    def _video(s):
        while s.run:
            try:
                r = urllib.request.urlopen(f"http://{s.host}:{PORT}/video", timeout=5); buf = b""
                while s.run:
                    d = r.read1(65536)
                    if not d: break
                    buf += d
                    while True:
                        a = buf.find(b"\xff\xd8"); b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
                        if a < 0 or b < 0:
                            if a < 0: buf = buf[-2:]
                            break
                        jpg, buf = buf[a:b + 2], buf[b + 2:]
                        f = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                        if f is not None: s.frame = f; s.seq += 1
            except Exception as e:
                s.err = str(e); time.sleep(1)
    def _audio(s):
        try: import sounddevice as sd
        except Exception: return
        def mk(dev):
            o = sd.RawOutputStream(samplerate=16000, channels=1, dtype="int16", device=dev); o.start(); return o
        while s.run:
            try:
                r = urllib.request.urlopen(f"http://{s.host}:{PORT}/audio", timeout=5)
                cur = s.out_dev; out = mk(cur); carry = b""
                while s.run:
                    d = r.read1(3200)
                    if not d: break
                    d = carry + d; n = len(d) // 2 * 2; carry = d[n:]; d = d[:n]
                    w = s.rec_audio
                    if w:
                        try: w.writeframes(d)
                        except Exception: pass
                    if cur != s.out_dev: out.close(); cur = s.out_dev; out = mk(cur)
                    if not s.mute: out.write(d)
                out.close()
            except Exception:
                time.sleep(1)

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
                    s.size = (f.shape[1], f.shape[0])
                    w = cv2.VideoWriter(s.path, cv2.VideoWriter_fourcc(*"mp4v"), s.fps, s.size)
                if (f.shape[1], f.shape[0]) != s.size: f = cv2.resize(f, s.size)
                tgt = int((time.time() - t0) * s.fps)
                while n <= tgt: w.write(f); n += 1
            time.sleep(0.005)
        if w: w.release()

def finalize(vtmp, atmp, final):
    try:
        import imageio_ffmpeg
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", vtmp] + (["-i", atmp] if atmp else []) + \
              ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"] + \
              (["-c:a", "aac", "-shortest"] if atmp else []) + [final]
        subprocess.run(cmd, capture_output=True, creationflags=deps.NOWIN)
        ok = os.path.exists(final)
    except Exception:
        ok = False
    if not ok and os.path.exists(vtmp): os.replace(vtmp, final)
    for p in (vtmp, atmp):
        if p and os.path.exists(p):
            try: os.remove(p)
            except Exception: pass

class App:
    def __init__(s):
        r = s.root = tk.Tk(); r.title("KX Cam"); r.geometry("1180x720"); r.configure(bg=BG)
        try: r.iconbitmap(os.path.join(BASE, "icon.ico"))
        except Exception: pass
        st = ttk.Style(); st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG); st.configure("TNotebook", background=BG)
        st.configure("TNotebook.Tab", padding=(10, 5)); st.configure("TButton", padding=6)
        st.configure("TCheckbutton", background=BG, foreground=FG); st.configure("TRadiobutton", background=BG, foreground=FG)
        s.c = Client(); s.last = None; s.seen = -1; s.vcam = None; s.rec = None; s.srec = None
        s.mode = tk.StringVar(value="usb"); s.ip = tk.StringVar(value="192.168.1.")
        s.status = tk.StringVar(value="Desligado"); s.front = False; s.rot = 0
        s.mirror = tk.BooleanVar(); s.vflip = tk.BooleanVar(); s.bri = 0.0; s.con = 1.0
        s.torch = tk.BooleanVar(); s.mute = tk.BooleanVar(); s.vc = tk.BooleanVar()
        s.n = 0; s.t0 = time.time(); s.fps = 0
        s.view = tk.Label(r, bg="black", text="KX Cam\nby João Francisco Vica Paulo", fg=AC, font=("Segoe UI", 18)); s.view.pack(side="left", fill="both", expand=True)
        side = tk.Frame(r, bg=BG, width=340); side.pack(side="right", fill="y"); side.pack_propagate(False)
        tk.Label(side, textvariable=s.status, bg=BG, fg=AC, font=("Segoe UI", 10, "bold")).pack(pady=(8, 0))
        nb = ttk.Notebook(side); nb.pack(fill="both", expand=True, padx=6, pady=6)
        tabs = {}
        for t in ("Ligação", "Câmara", "Imagem/Áudio", "Gravar"):
            f = tk.Frame(nb, bg=BG); nb.add(f, text=t); tabs[t] = f
        # --- Ligação
        p = tabs["Ligação"]
        ttk.Radiobutton(p, text="USB (recomendado, cabo + Depuração USB)", variable=s.mode, value="usb").pack(anchor="w", padx=8, pady=(12, 2))
        ttk.Radiobutton(p, text="Wi-Fi (IP do telemóvel)", variable=s.mode, value="wifi").pack(anchor="w", padx=8)
        ttk.Entry(p, textvariable=s.ip).pack(fill="x", padx=8, pady=6)
        s.bconn = ttk.Button(p, text="Conectar", command=s.connect); s.bconn.pack(fill="x", padx=8, pady=4)
        ttk.Button(p, text="Instalar app no telemóvel (USB)", command=s.install_apk).pack(fill="x", padx=8, pady=4)
        tk.Label(p, text="Wi-Fi/browser: http://IP:4747/video", bg=BG, fg="#94a3b8").pack(pady=10)
        # --- Câmara
        p = tabs["Câmara"]
        ttk.Button(p, text="Trocar câmara (frontal/traseira)", command=s.swap).pack(fill="x", padx=8, pady=(12, 4))
        ttk.Checkbutton(p, text="Flash / Lanterna", variable=s.torch, command=lambda: s.c.cmd(torch=int(s.torch.get()))).pack(anchor="w", padx=8)
        s.combo(p, "Resolução", ["480p", "720p", "1080p"], "720p", lambda v: s.c.cmd(res=v[:-1]))
        s.combo(p, "FPS", ["15", "24", "30", "60"], "30", lambda v: s.c.cmd(fps=v))
        s.scale(p, "Qualidade JPEG", 30, 100, 80, lambda v: s.c.cmd(q=int(v)))
        s.scale(p, "Zoom", 0, 100, 0, lambda v: s.c.cmd(zoom=round(v / 100, 2)))
        s.scale(p, "Exposição", -100, 100, 0, lambda v: s.c.cmd(ev=round(v / 100, 2)))
        ttk.Button(p, text="Focar ao centro", command=lambda: s.c.cmd(focus=1)).pack(fill="x", padx=8, pady=8)
        # --- Imagem/Áudio
        p = tabs["Imagem/Áudio"]
        ttk.Checkbutton(p, text="Espelhar", variable=s.mirror).pack(anchor="w", padx=8, pady=(12, 0))
        ttk.Checkbutton(p, text="Inverter (vertical)", variable=s.vflip).pack(anchor="w", padx=8)
        ttk.Button(p, text="Rodar 90°", command=lambda: setattr(s, "rot", (s.rot + 90) % 360)).pack(fill="x", padx=8, pady=4)
        s.scale(p, "Brilho", -100, 100, 0, lambda v: setattr(s, "bri", v), live=True)
        s.scale(p, "Contraste", 50, 200, 100, lambda v: setattr(s, "con", v / 100), live=True)
        ttk.Checkbutton(p, text="Silenciar microfone no PC", variable=s.mute, command=lambda: setattr(s.c, "mute", s.mute.get())).pack(anchor="w", padx=8, pady=(10, 0))
        devs = ["Predefinido"]
        try:
            import sounddevice as sd
            devs += [f"{i} - {d['name']}" for i, d in enumerate(sd.query_devices()) if d["max_output_channels"] > 0]
        except Exception: pass
        s.combo(p, "Saída de áudio (use VB-Cable p/ microfone virtual)", devs, "Predefinido",
                lambda v: setattr(s.c, "out_dev", None if v == "Predefinido" else int(v.split(" - ")[0])))
        ttk.Checkbutton(p, text="Câmara virtual (OBS Virtual Camera)", variable=s.vc, command=s.toggle_vcam).pack(anchor="w", padx=8, pady=10)
        # --- Gravar
        p = tabs["Gravar"]
        s.brec = ttk.Button(p, text="● Gravar vídeo da câmara", command=s.toggle_rec); s.brec.pack(fill="x", padx=8, pady=(14, 4))
        s.bsrec = ttk.Button(p, text="● Gravar ecrã do PC", command=s.toggle_screen); s.bsrec.pack(fill="x", padx=8, pady=4)
        ttk.Button(p, text="Abrir pasta das gravações", command=lambda: (os.makedirs(OUT, exist_ok=True), os.startfile(OUT))).pack(fill="x", padx=8, pady=4)
        tk.Label(p, text=OUT, bg=BG, fg="#94a3b8", wraplength=300).pack(pady=8)
        tk.Label(side, text="KX • by João Francisco Vica Paulo", bg=BG, fg=AC).pack(pady=6)
        r.protocol("WM_DELETE_WINDOW", s.close)
        threading.Thread(target=lambda: self_safe(deps.ensure_adb), daemon=True).start()
        s.tick(); r.mainloop()

    # --- widgets helpers
    def scale(s, p, txt, lo, hi, val, cb, live=False):
        ttk.Label(p, text=txt).pack(anchor="w", padx=8, pady=(8, 0))
        w = ttk.Scale(p, from_=lo, to=hi, value=val); w.pack(fill="x", padx=8)
        if live: w.configure(command=lambda v: cb(float(v)))
        else: w.bind("<ButtonRelease-1>", lambda e: cb(w.get()))
    def combo(s, p, txt, vals, init, cb):
        ttk.Label(p, text=txt).pack(anchor="w", padx=8, pady=(8, 0))
        c = ttk.Combobox(p, values=vals, state="readonly"); c.set(init); c.pack(fill="x", padx=8)
        c.bind("<<ComboboxSelected>>", lambda e: cb(c.get()))
    def st(s, t): s.root.after(0, lambda: s.status.set(t))

    # --- ligação
    def connect(s):
        if s.c.run:
            s.c.stop(); s.bconn.config(text="Conectar"); s.status.set("Desligado"); return
        s.bconn.config(text="Desligar"); threading.Thread(target=s._connect, daemon=True).start()
    def _connect(s):
        try:
            if s.mode.get() == "usb":
                s.st("A preparar ADB...")
                out = deps.adb("devices").stdout
                if not [l for l in out.splitlines()[1:] if l.strip().endswith("device")]:
                    raise RuntimeError("Nenhum telemóvel detetado.\nLigue o cabo, ative a Depuração USB e aceite o pedido no telemóvel.")
                deps.adb("forward", f"tcp:{PORT}", f"tcp:{PORT}")
                deps.adb("shell", "am", "start", "-n", "com.kx.cam/.MainActivity", "--ez", "autostart", "true")
                host = "127.0.0.1"
            else: host = s.ip.get().strip()
            s.c.start(host); s.st("A ligar a " + host + " ...")
        except Exception as e:
            s.root.after(0, lambda: (messagebox.showerror("KX Cam", str(e)), s.bconn.config(text="Conectar"), s.status.set("Desligado")))
    def install_apk(s):
        def go():
            apk = next((p for p in (os.path.join(BASE, "kxcam.apk"), os.path.join(os.path.dirname(sys.executable), "kxcam.apk")) if os.path.exists(p)), None)
            if not apk: apk = filedialog.askopenfilename(title="Escolha o APK do KX Cam", filetypes=[("APK", "*.apk")])
            if not apk: return
            s.st("A instalar APK..."); r = deps.adb("install", "-r", apk)
            s.root.after(0, lambda: messagebox.showinfo("KX Cam", (r.stdout + r.stderr).strip() or "Concluído"))
        threading.Thread(target=go, daemon=True).start()
    def swap(s):
        s.front = not s.front; s.c.cmd(cam="front" if s.front else "back")

    # --- imagem
    def process(s, f):
        if s.mirror.get(): f = cv2.flip(f, 1)
        if s.vflip.get(): f = cv2.flip(f, 0)
        if s.rot: f = cv2.rotate(f, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[s.rot])
        if s.bri or s.con != 1.0: f = cv2.convertScaleAbs(f, alpha=s.con, beta=s.bri)
        return f
    def toggle_vcam(s):
        if s.vc.get() and not deps.ensure_obs(): s.vc.set(False)
        if not s.vc.get() and s.vcam: s.vcam.close(); s.vcam = None
    def send_vcam(s, f):
        try:
            import pyvirtualcam
            h, w = f.shape[:2]
            if s.vcam is None or (s.vcam.width, s.vcam.height) != (w, h):
                if s.vcam: s.vcam.close()
                s.vcam = pyvirtualcam.Camera(w, h, 30, fmt=pyvirtualcam.PixelFormat.BGR)
            s.vcam.send(f)
        except Exception as e:
            s.vc.set(False); s.vcam = None; messagebox.showerror("KX Cam", f"Câmara virtual indisponível:\n{e}")
    def tick(s):
        f = s.c.frame
        if f is not None and s.c.seq != s.seen:
            s.seen = s.c.seq; s.n += 1; f = s.process(f); s.last = f
            if s.vc.get(): s.send_vcam(f)
            h, w = f.shape[:2]; cw, ch = max(s.view.winfo_width(), 2), max(s.view.winfo_height(), 2)
            sc = min(cw / w, ch / h)
            img = cv2.resize(f, (max(int(w * sc), 1), max(int(h * sc), 1)))
            ph = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            s.view.configure(image=ph, text=""); s.view.image = ph
        if time.time() - s.t0 >= 1:
            s.fps = s.n; s.n = 0; s.t0 = time.time()
            if s.c.run:
                s.status.set(f"● Ligado  {s.last.shape[1]}x{s.last.shape[0]}  {s.fps} fps" if s.last is not None and s.fps else "A aguardar vídeo do telemóvel...")
        s.root.after(15, s.tick)

    # --- gravação
    def toggle_rec(s):
        if s.rec is None:
            if s.last is None: return messagebox.showwarning("KX Cam", "Ligue a câmara primeiro.")
            os.makedirs(OUT, exist_ok=True); ts = time.strftime("%Y%m%d_%H%M%S")
            s.rv, s.ra, s.rf = os.path.join(OUT, f"_{ts}.mp4"), os.path.join(OUT, f"_{ts}.wav"), os.path.join(OUT, f"Camera_{ts}.mp4")
            wf = wave.open(s.ra, "wb"); wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            s.rwf = wf; s.c.rec_audio = wf
            s.rec = Rec(lambda: s.last, s.rv, 30); s.rec.start(); s.brec.config(text="■ Parar gravação da câmara")
        else:
            s.c.rec_audio = None; s.rec.on = False; s.rec.join(); s.rwf.close()
            threading.Thread(target=finalize, args=(s.rv, s.ra, s.rf), daemon=True).start()
            s.rec = None; s.brec.config(text="● Gravar vídeo da câmara")
            messagebox.showinfo("KX Cam", "Gravação guardada em:\n" + s.rf)
    def toggle_screen(s):
        if s.srec is None:
            os.makedirs(OUT, exist_ok=True); ts = time.strftime("%Y%m%d_%H%M%S")
            s.sv, s.sf = os.path.join(OUT, f"_{ts}s.mp4"), os.path.join(OUT, f"Ecra_{ts}.mp4")
            s.srec = Rec(ScreenGrab(), s.sv, 20); s.srec.start(); s.bsrec.config(text="■ Parar gravação do ecrã")
        else:
            s.srec.on = False; s.srec.join()
            threading.Thread(target=finalize, args=(s.sv, None, s.sf), daemon=True).start()
            s.srec = None; s.bsrec.config(text="● Gravar ecrã do PC")
            messagebox.showinfo("KX Cam", "Gravação guardada em:\n" + s.sf)
    def close(s):
        for r in (s.rec, s.srec):
            if r: r.on = False
        s.c.stop()
        if s.vcam: s.vcam.close()
        s.root.destroy()

def self_safe(fn):
    try: fn()
    except Exception: pass

if __name__ == "__main__":
    App()
