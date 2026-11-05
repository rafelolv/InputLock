#define AppName "InputLock"
#define Version "1.0.2"
#define Author "rafaelolv"
#define URL "https://github.com/rafelolv/InputLock"
#define ExeName "InputLock.exe"

[Setup]
AppId={{941F422E-40A8-4C04-86ED-91355C9FBEA4}
AppName={#AppName}
AppVersion={#Version}
AppPublisher={#Author}
AppPublisherURL=https://github.com/rafelolv
AppSupportURL={#URL}/issues
AppUpdatesURL={#URL}/releases
DefaultDirName={localappdata}\Programs\{#AppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=InputLock-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
LicenseFile=LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
