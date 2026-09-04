; Inno Setup 6 installer for the staged Windows onedir tree.
; Mechanics: docs/windows-freeze.md
; Compile on Windows after staging dist\cleave\:
;   iscc /DAppVersion=X.Y.Z packaging\windows\cleave.iss
; AppVersion is injected from cleave.__version__; never hardcode it here.

#ifndef AppVersion
  #error AppVersion must be defined: iscc /DAppVersion=X.Y.Z
#endif

#ifndef DistDir
  #define DistDir "..\..\dist\cleave"
#endif

[Setup]
; Fixed for the life of the product so later versions upgrade in place.
AppId={{caf89057-3432-458e-a1de-1dba1176a4ba}
AppName=Cleave
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=SpoddyCoder
AppPublisherURL=https://github.com/SpoddyCoder/cleave
UninstallDisplayName=Cleave
DefaultDirName={autopf}\Cleave
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\LICENSE
OutputDir=..\..
OutputBaseFilename=cleave-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ChangesEnvironment=yes
; Uninstall removes {app} only. Documents\cleave\ and %APPDATA%\cleave\ stay.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add Cleave to the PATH"; GroupDescription: "PATH"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Cleave"; Filename: "{app}\cleave.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Cleave"; Filename: "{app}\cleave.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Messages]
FinishedLabel=Setup has finished installing [name] on your computer.%n%nUninstall removes only the program folder. Projects in Documents\cleave\ and settings in %%APPDATA%%\cleave\ are left in place.
UninstalledAllLabel=[name] was successfully removed from your computer.%n%nProjects in Documents\cleave\ and settings in %%APPDATA%%\cleave\ were left in place.
ConfirmUninstall=Remove %1 from your computer?%n%nProjects in Documents\cleave\ and settings in %%APPDATA%%\cleave\ will be left in place.

[Code]
const
  EnvironmentKeyMachine =
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  EnvironmentKeyUser = 'Environment';

function EnvironmentRootKey: Integer;
begin
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function EnvironmentSubKey: String;
begin
  if IsAdminInstallMode then
    Result := EnvironmentKeyMachine
  else
    Result := EnvironmentKeyUser;
end;

function NormalizedDir(const Dir: String): String;
begin
  Result := RemoveBackslash(Trim(Dir));
end;

function PathListContainsDir(const Paths, Dir: String): Boolean;
var
  Padded, Needle: String;
begin
  Padded := ';' + Uppercase(Paths) + ';';
  Needle := ';' + Uppercase(NormalizedDir(Dir)) + ';';
  Result := Pos(Needle, Padded) > 0;
  if not Result then
  begin
    Needle := ';' + Uppercase(NormalizedDir(Dir)) + '\;';
    Result := Pos(Needle, Padded) > 0;
  end;
end;

procedure AddAppToPath;
var
  AppDir, Paths: String;
begin
  AppDir := ExpandConstant('{app}');
  if not RegQueryStringValue(EnvironmentRootKey, EnvironmentSubKey, 'Path', Paths) then
    Paths := '';
  if PathListContainsDir(Paths, AppDir) then
    Exit;
  if Trim(Paths) = '' then
    Paths := AppDir
  else if Paths[Length(Paths)] = ';' then
    Paths := Paths + AppDir
  else
    Paths := Paths + ';' + AppDir;
  if not RegWriteExpandStringValue(EnvironmentRootKey, EnvironmentSubKey, 'Path', Paths) then
    Log('Could not add {app} to PATH');
end;

procedure RemoveAppFromPath;
var
  AppDir, Paths, Entry, Rebuilt: String;
  I, StartPos: Integer;
begin
  AppDir := NormalizedDir(ExpandConstant('{app}'));
  if not RegQueryStringValue(EnvironmentRootKey, EnvironmentSubKey, 'Path', Paths) then
    Exit;
  if not PathListContainsDir(Paths, AppDir) then
    Exit;
  Rebuilt := '';
  StartPos := 1;
  Paths := Paths + ';';
  for I := 1 to Length(Paths) do
  begin
    if Paths[I] = ';' then
    begin
      Entry := Copy(Paths, StartPos, I - StartPos);
      StartPos := I + 1;
      if (Trim(Entry) <> '') and
         (CompareText(NormalizedDir(Entry), AppDir) <> 0) then
      begin
        if Rebuilt <> '' then
          Rebuilt := Rebuilt + ';';
        Rebuilt := Rebuilt + Entry;
      end;
    end;
  end;
  if not RegWriteExpandStringValue(EnvironmentRootKey, EnvironmentSubKey, 'Path', Rebuilt) then
    Log('Could not remove {app} from PATH');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddAppToPath;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveAppFromPath;
end;
