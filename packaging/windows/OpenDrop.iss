; OpenDrop - installeur Windows (Inno Setup 6)
;
; - elevation admin obligatoire, installation dans Program Files (x86)
; - dependances Python installees en venv local a partir des wheels fournis
;   (aucun acces reseau necessaire au moment de l'installation)
; - desinstallation : nettoie l'application ET ses donnees (config, session,
;   certificats, venv) MAIS NE TOUCHE JAMAIS aux dossiers de reception et
;   de partage (les "data" de l'utilisateur restent sur le disque)
;
; Compilation (la CI le fait automatiquement) :
;   iscc packaging\windows\OpenDrop.iss /DMyAppVersion=0.2.0

#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
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
; Installation systeme : elevation admin requise.
PrivilegesRequired=admin
; Binaire x64 uniquement.
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
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Bundle prepare par la CI : binaire + src/ + web/ + pyproject + wheels + docs
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\OpenDrop.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\OpenDrop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OpenDrop.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Installe les dependances dans {app}\venv (hors-ligne, a partir des wheels).
// Code retour : 1 = Python absent ou trop vieux, 2 = echec venv/pip.
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
begin
  if CurStep = ssPostInstall then
  begin
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
        MsgBox('Python 3.10+ est requis pour faire tourner OpenDrop.'#13#10#13#10 +
               '1. Installez Python depuis https://www.python.org/downloads/'#13#10 +
               '   (cochez "Add python.exe to PATH").'#13#10 +
               '2. Relancez ce setup.'#13#10#13#10 +
               'L installation va etre annulee.', mbError, MB_OK);
        Abort;
      end
      else if ResultCode <> 0 then
      begin
        MsgBox('Echec de l installation des dependances Python (code ' +
               IntToStr(ResultCode) + ').'#13#10#13#10 +
               'Relancez ce setup ; si le probleme persiste, verifiez que'#13#10 +
               'python.exe -m pip fonctionne bien.'#13#10#13#10 +
               'L installation va etre annulee.', mbError, MB_OK);
        Abort;
      end;
    end
    else
    begin
      MsgBox('Impossible de lancer le script d installation des dependances.',
             mbError, MB_OK);
      Abort;
    end;
  end;
end;

// Desinstallation : arbre de processus + venv + donnees applicatives.
// Les dossiers de reception et de partage (config download_directory /
// share_directory, generalement dans Downloads) ne sont JAMAIS supprimes.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    // L'application lance python en enfant : on tue tout l'arbre.
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM OpenDrop.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // venv cree au-dela de la liste des fichiers installes (Inno ne le
    // connait pas) : il faut le retirer explicitement.
    DelTree(ExpandConstant('{app}\venv'), True, True, True);

    // Donnees applicatives de l'application uniquement (fichiers connus).
    // Aucune suppression recursive du dossier : les fichiers recus et les
    // fichiers partages, ou qu'ils soient, restent intacts.
    DataDir := ExpandConstant('{localappdata}\OpenDrop');
    DeleteFile(DataDir + '\config.json');
    DeleteFile(DataDir + '\session.json');
    DeleteFile(DataDir + '\server.pid');
    DelTree(DataDir + '\certs', True, True, True);
    RemoveDir(DataDir); // n'a lieu que si le dossier est devenu vide
  end;
end;
