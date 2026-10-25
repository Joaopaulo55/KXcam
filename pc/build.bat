@echo off
REM KX Cam PC - gera dist\KXCam.exe  (requer Python 3.10+ no PC)
py -m pip install -r requirements.txt
py -m PyInstaller --noconfirm --onefile --windowed --name KXCam --icon icon.ico --add-data "icon.png;." --add-data "icon.ico;." ^
  --collect-all imageio_ffmpeg --collect-all sounddevice --collect-all _sounddevice_data --collect-all pyvirtualcam kxcam.py
echo.
echo Pronto: dist\KXCam.exe  - agora compile installer.iss com o Inno Setup (opcional)
pause
