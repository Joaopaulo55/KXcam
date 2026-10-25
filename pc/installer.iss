[Setup]
AppName=KX Cam
AppVersion=1.0
AppPublisher=KX by João Francisco Vica Paulo
DefaultDirName={autopf}\KXCam
OutputBaseFilename=KXCam_Setup
SetupIconFile=icon.ico
Compression=lzma2
[Files]
Source: "dist\KXCam.exe"; DestDir: "{app}"
Source: "icon.ico"; DestDir: "{app}"
Source: "kxcam.apk"; DestDir: "{app}"; Flags: skipifsourcedoesntexist
[Icons]
Name: "{autoprograms}\KX Cam"; Filename: "{app}\KXCam.exe"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\KX Cam"; Filename: "{app}\KXCam.exe"; IconFilename: "{app}\icon.ico"
[Run]
; Dependência: Visual C++ Runtime - descarrega e instala só se não existir
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Invoke-WebRequest https://aka.ms/vs/17/release/vc_redist.x64.exe -OutFile $env:TEMP\vc.exe; Start-Process $env:TEMP\vc.exe -ArgumentList '/install /quiet /norestart' -Wait"""; StatusMsg: "A instalar dependências (VC++)..."; Check: NeedVC; Flags: runhidden
Filename: "{app}\KXCam.exe"; Description: "Abrir KX Cam"; Flags: nowait postinstall skipifsilent
[Code]
function NeedVC: Boolean;
begin
  Result := not RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;
