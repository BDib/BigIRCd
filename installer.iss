; --- BigIRCd Installation Script ---
#define MyAppName "BigIRCd"
#define MyAppVersion "1.0"
#define MyAppPublisher "B Dib"
#define MyAppExeName "BigIRCd.exe"

[Setup]
; Unique App ID
AppId={{A1B2C3D4-E5F6-G7H8-I9J0-K1L2M3N4O5P6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Fixed to install in %AppData% instead of Program Files [cite: 9]
DefaultDirName={userappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Targets Windows 7 SP1 and newer (64-bit) [cite: 9]
MinVersion=6.1sp1
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64os
; Icon for the installer itself [cite: 10]
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
OutputDir=dist\Installer
OutputBaseFilename=BigIRCd_Setup_x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable from your dist folder [cite: 11]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Configuration and documentation files [cite: 12]
Source: "MOTD.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "License.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "ReadMe.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu and Desktop shortcuts [cite: 14]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\View License"; Filename: "{app}\License.txt"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Launch the app after installation [cite: 14]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent