"""KX Cam - verificação/instalação automática de dependências (ADB, OBS Virtual Camera)."""
import os, shutil, subprocess, zipfile, urllib.request, webbrowser
from tkinter import messagebox

HOME = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "KXCam")
NOWIN = 0x08000000 if os.name == "nt" else 0
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

def adb_path():
    p = shutil.which("adb")
    if p: return p
    q = os.path.join(HOME, "platform-tools", "adb.exe")
    return q if os.path.exists(q) else None

def ensure_adb():
    if adb_path(): return adb_path()
    os.makedirs(HOME, exist_ok=True)
    z = os.path.join(HOME, "pt.zip")
    urllib.request.urlretrieve(ADB_URL, z)
    zipfile.ZipFile(z).extractall(HOME); os.remove(z)
    if not adb_path(): raise RuntimeError("Não foi possível instalar o ADB.")
    return adb_path()

def adb(*a):
    return subprocess.run([ensure_adb(), *a], capture_output=True, text=True, timeout=60, creationflags=NOWIN)

def obs_ok():
    try:
        r = subprocess.run(["reg", "query", r"HKCR\CLSID\{A3FCE0F5-3493-419F-958A-ABA1250EC20B}"],
                           capture_output=True, creationflags=NOWIN)
        return r.returncode == 0
    except Exception:
        return False

def ensure_obs():
    """Câmara virtual precisa do OBS Virtual Camera. Oferece instalar via winget."""
    if obs_ok(): return True
    if messagebox.askyesno("KX Cam", "Para usar a Câmara Virtual (Zoom, Teams, Discord...) é preciso o OBS Studio.\n\nInstalar agora (winget)?"):
        try:
            subprocess.run(["winget", "install", "-e", "--id", "OBSProject.OBSStudio", "--accept-source-agreements",
                            "--accept-package-agreements"], timeout=900)
        except Exception:
            webbrowser.open("https://obsproject.com/download")
        messagebox.showinfo("KX Cam", "Depois de instalar, abra o OBS uma vez, feche-o e reinicie o KX Cam.")
    else:
        webbrowser.open("https://obsproject.com/download")
    return False
