#define AppName "InputLock"
#define Version "1.0.5"
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
DisableReadyPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=InputLock-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
LicenseFile=LICENSE
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern dynamic windows11 includetitlebar
WizardBackColor=#f5f5f7
WizardBackColorDynamicDark=#20242b
WizardImageFile=assets\installer-sidebar.png
WizardImageFileDynamicDark=assets\installer-sidebar.png
WizardSmallImageFile=assets\installer-header.png
WizardSmallImageFileDynamicDark=assets\installer-header.png
WizardImageStretch=yes
WizardImageBackColor=#20242b
WizardImageBackColorDynamicDark=#20242b
ShowLanguageDialog=auto
CloseApplications=yes
CloseApplicationsFilter=InputLock.exe
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
brazilianportuguese.CleanupTitle=Desinstalar InputLock
brazilianportuguese.CleanupHeading=Dados do aplicativo
brazilianportuguese.CleanupDescription=O InputLock será removido. Você pode manter suas preferências para uma reinstalação.
brazilianportuguese.CleanupCheckbox=Apagar também configurações e dados locais
brazilianportuguese.CleanupWarning=Se marcada, esta opção apaga permanentemente os dados destas pastas:
brazilianportuguese.CleanupContinue=Continuar
brazilianportuguese.CleanupFailed=Alguns dados não puderam ser apagados. Confira a pasta:%n%1
english.CleanupTitle=Uninstall InputLock
english.CleanupHeading=Application data
english.CleanupDescription=InputLock will be removed. You can keep your preferences for a future installation.
english.CleanupCheckbox=Also delete settings and local data
english.CleanupWarning=When selected, this permanently deletes data in these folders:
english.CleanupContinue=Continue
english.CleanupFailed=Some data could not be deleted. Check this folder:%n%1

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\InputLock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveUserData: Boolean;

function ChooseCleanup: Boolean;
var
  Dialog: TSetupForm;
  Heading, Description, Warning, Paths: TNewStaticText;
  Checkbox: TNewCheckBox;
  ContinueButton: TNewButton;
begin
  Result := False;
  Dialog := CreateCustomForm(460, 300, True, True);
  try
    Dialog.Caption := CustomMessage('CleanupTitle');
    Dialog.Position := poScreenCenter;

    Heading := TNewStaticText.Create(Dialog);
    Heading.Parent := Dialog;
    Heading.Caption := CustomMessage('CleanupHeading');
    Heading.Font.Style := [fsBold];
    Heading.SetBounds(ScaleX(24), ScaleY(20), ScaleX(412), ScaleY(24));

    Description := TNewStaticText.Create(Dialog);
    Description.Parent := Dialog;
    Description.AutoSize := False;
    Description.WordWrap := True;
    Description.Caption := CustomMessage('CleanupDescription');
    Description.SetBounds(ScaleX(24), ScaleY(52), ScaleX(412), ScaleY(40));

    Checkbox := TNewCheckBox.Create(Dialog);
    Checkbox.Parent := Dialog;
    Checkbox.Caption := CustomMessage('CleanupCheckbox');
    Checkbox.Checked := False;
    Checkbox.SetBounds(ScaleX(24), ScaleY(100), ScaleX(412), ScaleY(24));

    Warning := TNewStaticText.Create(Dialog);
    Warning.Parent := Dialog;
    Warning.AutoSize := False;
    Warning.WordWrap := True;
    Warning.Caption := CustomMessage('CleanupWarning');
    Warning.SetBounds(ScaleX(24), ScaleY(136), ScaleX(412), ScaleY(34));

    Paths := TNewStaticText.Create(Dialog);
    Paths.Parent := Dialog;
    Paths.AutoSize := False;
    Paths.WordWrap := True;
    Paths.Caption := ExpandConstant('{userappdata}\InputLock') + #13#10 +
      ExpandConstant('{localappdata}\InputLock');
    Paths.SetBounds(ScaleX(24), ScaleY(174), ScaleX(412), ScaleY(56));

    ContinueButton := TNewButton.Create(Dialog);
    ContinueButton.Parent := Dialog;
    ContinueButton.Caption := CustomMessage('CleanupContinue');
    ContinueButton.Default := True;
    ContinueButton.ModalResult := mrOk;
    ContinueButton.SetBounds(ScaleX(326), ScaleY(254), ScaleX(110), ScaleY(28));

    if Dialog.ShowModal = mrOk then
      Result := Checkbox.Checked;
  finally
    Dialog.Free;
  end;
end;

function InitializeUninstall: Boolean;
begin
  // Silent removal preserves data unless explicitly requested otherwise.
  RemoveUserData := ExpandConstant('{param:PURGEDATA|0}') = '1';
  Result := True;
end;

procedure DeleteUserData(const Path: String);
begin
  if DirExists(Path) and not DelTree(Path, True, True, True) then
  begin
    Log('Could not fully remove InputLock data: ' + Path);
    SuppressibleMsgBox(FmtMessage(CustomMessage('CleanupFailed'), [Path]),
      mbInformation, MB_OK, IDOK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usUninstall) and not UninstallSilent then
    RemoveUserData := ChooseCleanup;
  if (CurUninstallStep = usPostUninstall) and RemoveUserData then
  begin
    // Only these app-owned data folders; never wildcard the install directory.
    DeleteUserData(ExpandConstant('{userappdata}\InputLock'));
    DeleteUserData(ExpandConstant('{localappdata}\InputLock'));
  end;
end;
