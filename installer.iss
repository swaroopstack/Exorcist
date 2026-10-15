; Exorcist Inno Setup script.
; Install Inno Setup 6 (https://jrsoftware.org/isinfo.php), then:
;   iscc installer.iss
; Output: Output\Exorcist-Setup-0.4.0.exe
#define MyAppName "Exorcist"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "Exorcist contributors"
#define MyAppURL "https://github.com/swaroopstack/Exorcist"
#define MyAppExeName "exorcist.exe"

[Setup]
AppId={{3F1B2E4A-7C9D-4E5F-8A6B-Exorcist01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=Exorcist-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Uncomment after code signing is set up:
;SignTool=default sign $f

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "scan --min-mb 50"; Description: "Run a first scan"; Flags: nowait postinstall skipifsilent
