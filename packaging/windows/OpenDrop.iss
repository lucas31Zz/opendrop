; OpenDrop - Windows installer (Inno Setup 6)
;
; - admin elevation required, installs into Program Files (x86)
; - Python dependencies installed into a local venv from the bundled wheels
;   (no network access needed at install time)
; - refuses to downgrade an existing newer installation (see InitializeSetup)
; - language task: seeds %LOCALAPPDATA%\OpenDrop\config.json with the
;   chosen application language (English default, French optional)
; - uninstall: cleans the application AND its data (config, session,
;   certificates, venv) but NEVER touches the receive and share folders
;   (user "data" stays on disk)
;
; Compilation (done automatically by CI):
;   iscc packaging\windows\OpenDrop.iss /DMyAppVersion=0.10.0

#ifndef MyAppVersion
  #define MyAppVersion "0.10.0"
#endif
#define MyAppName "OpenDrop"
#define MyAppPublisher "lucas31Zz"
#define MyAppURL "https://github.com/lucas31Zz/opendrop"
#define BundleDir "..\..\publish\win"
#define IconFile "..\..\desktop\OpenDrop\app.ico"

[Setup]
AppId={{2E6B1C1B-5C2F-4A87-9E3D-8B5A0C7F4D62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf32}\OpenDrop
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; System-wide install: admin elevation required.
PrivilegesRequired=admin
; x64 only.
ArchitecturesAllowed=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=OpenDrop-{#MyAppVersion}-win-x64-setup
SetupIconFile={#IconFile}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\OpenDrop.exe
UninstallDisplayName={#MyAppName}
CloseApplications=yes
ChangesAssociations=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Application language (radio group, English pre-selected).
Name: "lang\en"; Description: "English"; GroupDescription: "Application language:"; Flags: exclusive
Name: "lang\fr"; Description: "Fran#231ais"; GroupDescription: "Application language:"; Flags: exclusive unchecked

[Files]
; Bundle prepared by the CI: binary + src/ + web/ + pyproject + wheels + docs
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\OpenDrop.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\OpenDrop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OpenDrop.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Setup exit codes, read by the updater after a silent install
// (UpdateService.ApplyWindows records them, the app reports them on its
// next start). In silent mode they are the ONLY signal: MsgBox is skipped
// there because an unattended setup has nowhere to show it and would
// simply stall, and Abort would return 0 and look like a success.
//   1 = Python missing or too old
//   2 = the dependencies could not be installed
//   3 = the dependency script could not be launched at all
function ExitProcess(uExitCode: UINT): BOOL;
  external 'ExitProcess@kernel32.dll stdcall';

// Downgrade guard: refuse to install an older version over a newer one
// (DisplayVersion comes from AppVersion, i.e. "v0.7.0" from CI or "0.7.0"
// from a local build). Equal versions reinstall normally.
function CompareDottedVersions(const V1, V2: String): Integer;
var
  Left, Right, Piece1, Piece2: String;
  N1, N2, P: Integer;
begin
  Result := 0;
  Left := V1;
  Right := V2;
  if (Length(Left) > 0) and ((Left[1] = 'v') or (Left[1] = 'V')) then
    Delete(Left, 1, 1);
  if (Length(Right) > 0) and ((Right[1] = 'v') or (Right[1] = 'V')) then
    Delete(Right, 1, 1);
  while (Result = 0) and ((Left <> '') or (Right <> '')) do
  begin
    P := Pos('.', Left);
    if P > 0 then
    begin
      Piece1 := Copy(Left, 1, P - 1);
      Delete(Left, 1, P);
    end
    else
    begin
      Piece1 := Left;
      Left := '';
    end;
    P := Pos('.', Right);
    if P > 0 then
    begin
      Piece2 := Copy(Right, 1, P - 1);
      Delete(Right, 1, P);
    end
    else
    begin
      Piece2 := Right;
      Right := '';
    end;
    N1 := StrToIntDef(Trim(Piece1), 0);
    N2 := StrToIntDef(Trim(Piece2), 0);
    if N1 > N2 then
      Result := 1
    else if N1 < N2 then
      Result := -1;
  end;
end;

function InitializeSetup(): Boolean;
var
  Installed: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{2E6B1C1B-5C2F-4A87-9E3D-8B5A0C7F4D62}_is1',
    'DisplayVersion', Installed) then
  begin
    if (Installed <> '') and (CompareDottedVersions(Installed, '{#MyAppVersion}') > 0) then
    begin
      // No dialog when running silently (the updater only ever installs a
      // newer release, but a manual /VERYSILENT downgrade must not block).
      if not WizardSilent then
        MsgBox('OpenDrop ' + Installed + ' is already installed, but this setup installs ' +
               '{#MyAppVersion}.'#13#10#13#10 +
               'Downgrading is not supported: nothing was changed. Uninstall OpenDrop ' +
               Installed + ' first, or use the release matching it.',
               mbError, MB_OK);
      Result := False;
    end;
  end;
end;

// Installs the dependencies into {app}\venv (offline, from the bundled wheels).
// Reports the failure through the setup exit code (see ExitProcess above).
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
  ConfigDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Seed the application language chosen on the tasks page, but only
    // when the user picked French and no config exists yet (never
    // overwrite an existing configuration).
    if WizardIsTaskSelected('lang\fr') and
       not FileExists(ExpandConstant('{localappdata}\OpenDrop\config.json')) then
    begin
      ConfigDir := ExpandConstant('{localappdata}\OpenDrop');
      ForceDirectories(ConfigDir);
      SaveStringToFile(ConfigDir + '\config.json', '{"language":"fr"}', False);
    end;

    Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{app}\install-deps.ps1') +
      '" -WheelDir "' + ExpandConstant('{app}\wheels') +
      '" -VenvDir "' + ExpandConstant('{app}\venv') +
      '" -Requirements "' + ExpandConstant('{app}\requirements.txt') + '"';

    if Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
            Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode = 1 then
      begin
        if not WizardSilent then
          MsgBox('Python 3.10+ is required to run OpenDrop.'#13#10#13#10 +
                 '1. Install Python from https://www.python.org/downloads/'#13#10 +
                 '   (check "Add python.exe to PATH").'#13#10 +
                 '2. Run this setup again.'#13#10#13#10 +
                 'The installation will now be cancelled.', mbError, MB_OK);
        ExitProcess(1);
      end
      else if ResultCode <> 0 then
      begin
        if not WizardSilent then
          MsgBox('Failed to install the Python dependencies (code ' +
                 IntToStr(ResultCode) + ').'#13#10#13#10 +
                 'Run this setup again; if the problem persists, check that'#13#10 +
                 'python.exe -m pip works.'#13#10#13#10 +
                 'The installation will now be cancelled.', mbError, MB_OK);
        ExitProcess(2);
      end;
    end
    else
    begin
      if not WizardSilent then
        MsgBox('Could not launch the dependency installation script.',
               mbError, MB_OK);
      ExitProcess(3);
    end;
  end;
end;

// Uninstall: process tree + venv + application data.
// The receive and share folders (config download_directory /
// share_directory, usually under Downloads) are NEVER deleted.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    // The app spawns python as a child: kill the whole tree.
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM OpenDrop.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // venv is created beyond the list of installed files (Inno does not
    // know about it): it must be removed explicitly.
    DelTree(ExpandConstant('{app}\venv'), True, True, True);

    // Application data files only (known files).
    // No recursive delete of the folder: received and shared files,
    // wherever they are, stay intact.
    DataDir := ExpandConstant('{localappdata}\OpenDrop');
    DeleteFile(DataDir + '\config.json');
    DeleteFile(DataDir + '\session.json');
    DeleteFile(DataDir + '\server.pid');
    DelTree(DataDir + '\certs', True, True, True);
    RemoveDir(DataDir); // only succeeds if the folder is now empty
  end;
end;
