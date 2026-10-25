"""KX Cam - build inteligente: verifica dependências, instala SÓ as que faltam, compila EXE (e instalador)."""
import importlib.util, subprocess, sys, os, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
NEED = {"cv2": "opencv-python", "numpy": "numpy", "PIL": "pillow", "customtkinter": "customtkinter",
        "sounddevice": "sounddevice", "mss": "mss", "pyvirtualcam": "pyvirtualcam",
        "imageio_ffmpeg": "imageio-ffmpeg", "PyInstaller": "pyinstaller"}
print("== KX Cam :: verificacao de dependencias ==")
missing = []
for mod, pkg in NEED.items():
    ok = importlib.util.find_spec(mod) is not None
    print(f"  [{'OK   ' if ok else 'FALTA'}] {pkg}")
    if not ok: missing.append(pkg)
if missing:
    print("\nA instalar so o que falta:", ", ".join(missing))
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
else:
    print("\nTudo instalado - nada para descarregar.")
if not os.path.exists("icon.ico"):
    subprocess.check_call([sys.executable, os.path.join("..", "make_icon.py")])
print("\n== A compilar KXCam.exe ==")
subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", "KXCam",
    "--icon", "icon.ico", "--add-data", "icon.png;.", "--add-data", "icon.ico;.",
    "--collect-all", "customtkinter", "--collect-all", "imageio_ffmpeg", "--collect-all", "sounddevice",
    "--collect-all", "_sounddevice_data", "--collect-all", "pyvirtualcam", "kxcam.py"])
iscc = shutil.which("iscc") or next((p for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe") if os.path.exists(p)), None)
if iscc:
    print("\n== A criar instalador (Inno Setup) =="); subprocess.call([iscc, "installer.iss"])
    print("Instalador: Output\\KXCam_Setup.exe")
else:
    print("\nInno Setup nao encontrado - instalador ignorado (opcional). EXE em dist\\KXCam.exe")
