; Inno Setup 6 installer for the staged Windows onedir tree.
; Mechanics: docs/dev/windows-freeze.md
; Compile on Windows after staging dist\cleave\:
;   iscc /DAppVersion=X.Y.Z packaging\windows\cleave.iss
; AppVersion is injected from cleave.__version__; never hardcode it here.
; CUDA extra uses DownloadTemporaryFile and GetSHA256OfFile (Inno Setup 6.4+).
; CI installs current Inno via choco install innosetup.

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
; Uninstall removes {app} only. Documents\Cleave\ and %APPDATA%\Cleave\ stay.

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
FinishedLabel=Setup has finished installing [name] on your computer.%n%nUninstall removes only the program folder. Projects in Documents\Cleave\ and settings in %%APPDATA%%\Cleave\ are left in place.
UninstalledAllLabel=[name] was successfully removed from your computer.%n%nProjects in Documents\Cleave\ and settings in %%APPDATA%%\Cleave\ were left in place.
ConfirmUninstall=Remove %1 from your computer?%n%nProjects in Documents\Cleave\ and settings in %%APPDATA%%\Cleave\ will be left in place.

[Code]
const
  EnvironmentKeyMachine =
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  EnvironmentKeyUser = 'Environment';
  { Pinned PyTorch cu130 wheels (cp310 win_amd64). docs/dev/windows-freeze.md
    URLs percent-encode + as %2B.  A literal + in the URL path is valid
    per RFC 3986 but Delphi THTTPClient (Inno Setup's HTTP stack) and the
    PyTorch R2 CDN are more reliable with the encoded form.
    File constants use - instead of + for a safe temp-dir name. }
  CudaTorchFile =
    'torch-2.12.0-cu130-cp310-cp310-win_amd64.whl';
  CudaTorchUrl =
    'https://download.pytorch.org/whl/cu130/torch-2.12.0%2Bcu130-cp310-cp310-win_amd64.whl';
  CudaTorchSha256 =
    '9cde3a3dbe675ee1558e7ee2d6be60aaa2b9562552d1b0a659c8edd6edd29318';
  CudaTorchaudioFile =
    'torchaudio-2.11.0-cu130-cp310-cp310-win_amd64.whl';
  CudaTorchaudioUrl =
    'https://download.pytorch.org/whl/cu130/torchaudio-2.11.0%2Bcu130-cp310-cp310-win_amd64.whl';
  CudaTorchaudioSha256 =
    '9bbd4470c74172be32d0e11efbcf5e8dc785f7403b8232c07aac575c8d96715f';
  CudaTorchcodecFile =
    'torchcodec-0.14.0-cu130-cp310-cp310-win_amd64.whl';
  CudaTorchcodecUrl =
    'https://download.pytorch.org/whl/cu130/torchcodec-0.14.0%2Bcu130-cp310-cp310-win_amd64.whl';
  CudaTorchcodecSha256 =
    'b4cfae4d2fd58467fccc528a1e31a0ec6fed6a4a49b9495dab50d2aada1918cf';
  CudaDownloadSizeLabel = '2 GB';
  CudaYesIndex = 0;
  CudaNoIndex = 1;
  CudaPackageCount = 5;
  CudaDistInfoCount = 3;

var
  NvidiaGpuDetected: Boolean;
  CudaPage: TInputOptionWizardPage;
  CudaLastLogPercent: Integer;

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

function HasNvidiaGpu: Boolean;
var
  Locator, Service, Controllers, Controller: Variant;
  I, Count: Integer;
  AdapterName: String;
begin
  Result := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('', 'root\cimv2');
    Controllers := Service.ExecQuery('SELECT Name FROM Win32_VideoController');
    Count := Integer(Controllers.Count);
    for I := 0 to Count - 1 do
    begin
      try
        Controller := Controllers.ItemIndex(I);
        AdapterName := Controller.Name;
        if Pos('NVIDIA', Uppercase(AdapterName)) > 0 then
        begin
          Result := True;
          Exit;
        end;
      except
        { Skip an unreadable adapter; keep scanning the rest. }
      end;
    end;
  except
    Result := False;
  end;
end;

function CudaPromptText: String;
begin
  Result :=
    'NVIDIA graphics card detected - do you wish to download the CUDA toolkit for faster stem splitting? (' +
    CudaDownloadSizeLabel + ')';
end;

function CudaParamRequested: Boolean;
begin
  Result := CompareText(Trim(ExpandConstant('{param:CUDA|0}')), '1') = 0;
end;

function ShouldDownloadCuda: Boolean;
begin
  if CudaParamRequested then
    Result := True
  else if WizardSilent then
    Result := False
  else
    Result := NvidiaGpuDetected and (CudaPage.SelectedValueIndex = CudaYesIndex);
end;

function CudaPackageName(Index: Integer): String;
begin
  case Index of
    0: Result := 'torch';
    1: Result := 'functorch';
    2: Result := 'torchgen';
    3: Result := 'torchaudio';
    4: Result := 'torchcodec';
  else
    Result := '';
  end;
end;

function CudaDistInfoPrefix(Index: Integer): String;
begin
  case Index of
    0: Result := 'torch-';
    1: Result := 'torchaudio-';
    2: Result := 'torchcodec-';
  else
    Result := '';
  end;
end;

procedure WarnCudaFailure(const Message: String);
begin
  Log(Message);
  if not WizardSilent then
    MsgBox(Message, mbInformation, MB_OK);
end;

function OnCudaDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
var
  Percent: Integer;
begin
  Percent := 0;
  if ProgressMax > 0 then
    Percent := Integer((Progress * 100) div ProgressMax);
  if not WizardSilent then
  begin
    WizardForm.FilenameLabel.Caption := FileName;
    if ProgressMax > 0 then
    begin
      WizardForm.ProgressGauge.Max := 1000;
      WizardForm.ProgressGauge.Position := Integer((Progress * 1000) div ProgressMax);
      WizardForm.StatusLabel.Caption :=
        Format('Downloading CUDA toolkit (%s)... %d%%', [FileName, Percent]);
    end
    else
      WizardForm.StatusLabel.Caption :=
        'Downloading CUDA toolkit (' + FileName + ')...';
  end;
  if (ProgressMax > 0) and ((Percent = 100) or (Percent >= CudaLastLogPercent + 10)) then
  begin
    Log(Format('CUDA download %s: %d%%', [FileName, Percent]));
    CudaLastLogPercent := Percent;
  end;
  Result := True;
end;

function DownloadCudaWheel(const Url, BaseName, Sha256: String;
  var Reason: String): Boolean;
var
  Dest, Got: String;
begin
  Result := False;
  Reason := '';
  Dest := ExpandConstant('{tmp}\') + BaseName;
  CudaLastLogPercent := 0;
  if FileExists(Dest) then
    DeleteFile(Dest);
  try
    DownloadTemporaryFile(Url, BaseName, '', @OnCudaDownloadProgress);
  except
    Reason := GetExceptionMessage;
    Log('CUDA download failed for ' + BaseName + ': ' + Reason);
    if FileExists(Dest) then
      DeleteFile(Dest);
    Exit;
  end;
  if not FileExists(Dest) then
  begin
    Reason := 'file missing after download';
    Log('CUDA wheel missing after download: ' + BaseName);
    Exit;
  end;
  try
    Got := Lowercase(GetSHA256OfFile(Dest));
  except
    Reason := 'SHA-256 read failed: ' + GetExceptionMessage;
    Log('CUDA SHA-256 read failed for ' + BaseName + ': ' + GetExceptionMessage);
    DeleteFile(Dest);
    Exit;
  end;
  if CompareText(Got, Lowercase(Sha256)) <> 0 then
  begin
    Reason := 'SHA-256 mismatch (got ' + Got + ')';
    Log('CUDA SHA-256 mismatch for ' + BaseName + ' got ' + Got);
    DeleteFile(Dest);
    Exit;
  end;
  Result := True;
end;

function RunHidden(const Filename, Params: String; var ResultCode: Integer): Boolean;
begin
  Result := Exec(Filename, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function ExtractCudaWheel(const WheelPath, DestDir: String;
  var Reason: String): Boolean;
var
  ResultCode: Integer;
  Tar, ZipPath, Ps: String;
begin
  Result := False;
  Reason := '';
  if not DirExists(DestDir) then
    if not ForceDirectories(DestDir) then
    begin
      Reason := 'could not create ' + DestDir;
      Log('Could not create CUDA unpack dir ' + DestDir);
      Exit;
    end;
  Tar := ExpandConstant('{sys}\tar.exe');
  if FileExists(Tar) then
  begin
    Result := RunHidden(Tar, '-xf "' + WheelPath + '" -C "' + DestDir + '"', ResultCode) and
      (ResultCode = 0);
    if not Result then
    begin
      Reason := 'tar exit code ' + IntToStr(ResultCode);
      Log('tar extract failed rc=' + IntToStr(ResultCode) + ' for ' + WheelPath);
    end;
    Exit;
  end;
  Log('tar.exe not found; trying PowerShell Expand-Archive');
  ZipPath := WheelPath + '.zip';
  if FileExists(ZipPath) then
    DeleteFile(ZipPath);
  if not FileCopy(WheelPath, ZipPath, False) then
  begin
    Reason := 'could not copy wheel to .zip';
    Log('Could not copy wheel to .zip for Expand-Archive: ' + WheelPath);
    Exit;
  end;
  Ps := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Result := RunHidden(
    Ps,
    '-NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''' +
      ZipPath + ''' -DestinationPath ''' + DestDir + ''' -Force"',
    ResultCode) and (ResultCode = 0);
  DeleteFile(ZipPath);
  if not Result then
  begin
    Reason := 'Expand-Archive exit code ' + IntToStr(ResultCode);
    Log('Expand-Archive failed rc=' + IntToStr(ResultCode) + ' for ' + WheelPath);
  end;
end;

function DelTreeIfExists(const Path: String): Boolean;
begin
  Result := True;
  if DirExists(Path) then
    Result := DelTree(Path, True, True, True)
  else if FileExists(Path) then
    Result := DeleteFile(Path);
end;

function MoveDirTree(const Src, Dest: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not DirExists(Src) then
  begin
    Result := True;
    Exit;
  end;
  if not DelTreeIfExists(Dest) then
    Exit;
  if not ForceDirectories(ExtractFileDir(Dest)) then
    Exit;
  Result := RunHidden(
    ExpandConstant('{cmd}'),
    '/c move /Y "' + Src + '" "' + Dest + '"',
    ResultCode) and (ResultCode = 0);
  if not Result then
    Log('move failed rc=' + IntToStr(ResultCode) + ' ' + Src + ' -> ' + Dest);
end;

function CopyDirTree(const Src, Dest: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not DirExists(Src) then
  begin
    Result := True;
    Exit;
  end;
  Result := RunHidden(
    ExpandConstant('{cmd}'),
    '/c xcopy /E /I /Y /Q "' + Src + '" "' + Dest + '"',
    ResultCode) and (ResultCode = 0);
  if not Result then
    Log('xcopy failed rc=' + IntToStr(ResultCode) + ' ' + Src + ' -> ' + Dest);
end;

procedure ForEachMatchingDir(const Parent, Pattern: String; const DestParent: String; const DoMove: Boolean);
var
  FindRec: TFindRec;
  Src, Dest: String;
begin
  if not DirExists(Parent) then
    Exit;
  if FindFirst(AddBackslash(Parent) + Pattern, FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and
           (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          Src := AddBackslash(Parent) + FindRec.Name;
          if DestParent <> '' then
          begin
            Dest := AddBackslash(DestParent) + FindRec.Name;
            if DoMove then
              MoveDirTree(Src, Dest)
            else
              CopyDirTree(Src, Dest);
          end
          else
            DelTreeIfExists(Src);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function BackupCudaTargets(const InternalDir, BackupDir: String): Boolean;
var
  I: Integer;
  Name: String;
begin
  Result := False;
  if not ForceDirectories(BackupDir) then
    Exit;
  for I := 0 to CudaPackageCount - 1 do
  begin
    Name := CudaPackageName(I);
    if DirExists(AddBackslash(InternalDir) + Name) then
      if not MoveDirTree(AddBackslash(InternalDir) + Name, AddBackslash(BackupDir) + Name) then
        Exit;
  end;
  for I := 0 to CudaDistInfoCount - 1 do
    ForEachMatchingDir(InternalDir, CudaDistInfoPrefix(I) + '*.dist-info', BackupDir, True);
  Result := True;
end;

function RestoreCudaTargets(const InternalDir, BackupDir: String): Boolean;
var
  I: Integer;
  Name: String;
begin
  Result := True;
  for I := 0 to CudaPackageCount - 1 do
  begin
    Name := CudaPackageName(I);
    DelTreeIfExists(AddBackslash(InternalDir) + Name);
    if DirExists(AddBackslash(BackupDir) + Name) then
      if not MoveDirTree(AddBackslash(BackupDir) + Name, AddBackslash(InternalDir) + Name) then
        Result := False;
  end;
  for I := 0 to CudaDistInfoCount - 1 do
  begin
    ForEachMatchingDir(InternalDir, CudaDistInfoPrefix(I) + '*.dist-info', '', False);
    ForEachMatchingDir(BackupDir, CudaDistInfoPrefix(I) + '*.dist-info', InternalDir, True);
  end;
end;

function InstallStagedCudaPackages(const Staging, InternalDir: String): Boolean;
var
  I: Integer;
  Name: String;
begin
  Result := False;
  for I := 0 to CudaPackageCount - 1 do
  begin
    Name := CudaPackageName(I);
    if DirExists(AddBackslash(Staging) + Name) then
      if not CopyDirTree(AddBackslash(Staging) + Name, AddBackslash(InternalDir) + Name) then
        Exit;
  end;
  for I := 0 to CudaDistInfoCount - 1 do
    ForEachMatchingDir(Staging, CudaDistInfoPrefix(I) + '*.dist-info', InternalDir, False);
  Result := True;
end;

function ReplaceCudaPackages(const Staging, InternalDir: String): Boolean;
var
  BackupDir: String;
begin
  Result := False;
  BackupDir := ExpandConstant('{tmp}\cuda-cpu-bak');
  DelTreeIfExists(BackupDir);
  if not BackupCudaTargets(InternalDir, BackupDir) then
  begin
    Log('CUDA backup of CPU packages failed; restoring');
    RestoreCudaTargets(InternalDir, BackupDir);
    Exit;
  end;
  if not InstallStagedCudaPackages(Staging, InternalDir) then
  begin
    Log('CUDA copy into _internal failed; restoring CPU packages');
    RestoreCudaTargets(InternalDir, BackupDir);
    Exit;
  end;
  DelTreeIfExists(BackupDir);
  Result := True;
end;

procedure MaybeInstallCudaExtra;
var
  Staging, InternalDir, Tmp, Reason: String;
begin
  if not ShouldDownloadCuda then
  begin
    Log('CUDA extra not requested; leaving CPU torch');
    Exit;
  end;
  if CudaParamRequested then
    Log('Installing CUDA extra (/CUDA=1)')
  else
    Log('Installing CUDA extra (wizard Yes)');
  Tmp := ExpandConstant('{tmp}');
  Staging := Tmp + '\cuda-unpack';
  InternalDir := ExpandConstant('{app}\_internal');
  DelTreeIfExists(Staging);
  Reason := '';
  if not DownloadCudaWheel(CudaTorchUrl, CudaTorchFile, CudaTorchSha256, Reason) then
  begin
    WarnCudaFailure(
      'CUDA download failed (' + CudaTorchFile + '): ' + Reason + #13#10 +
      'URL: ' + CudaTorchUrl + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not DownloadCudaWheel(CudaTorchaudioUrl, CudaTorchaudioFile, CudaTorchaudioSha256, Reason) then
  begin
    WarnCudaFailure(
      'CUDA download failed (' + CudaTorchaudioFile + '): ' + Reason + #13#10 +
      'URL: ' + CudaTorchaudioUrl + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not DownloadCudaWheel(CudaTorchcodecUrl, CudaTorchcodecFile, CudaTorchcodecSha256, Reason) then
  begin
    WarnCudaFailure(
      'CUDA download failed (' + CudaTorchcodecFile + '): ' + Reason + #13#10 +
      'URL: ' + CudaTorchcodecUrl + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not WizardSilent then
    WizardForm.StatusLabel.Caption := 'Unpacking CUDA toolkit...';
  if not ExtractCudaWheel(Tmp + '\' + CudaTorchFile, Staging, Reason) then
  begin
    WarnCudaFailure(
      'CUDA unpack failed (' + CudaTorchFile + '): ' + Reason + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not ExtractCudaWheel(Tmp + '\' + CudaTorchaudioFile, Staging, Reason) then
  begin
    WarnCudaFailure(
      'CUDA unpack failed (' + CudaTorchaudioFile + '): ' + Reason + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not ExtractCudaWheel(Tmp + '\' + CudaTorchcodecFile, Staging, Reason) then
  begin
    WarnCudaFailure(
      'CUDA unpack failed (' + CudaTorchcodecFile + '): ' + Reason + #13#10#13#10 +
      'Stem splitting will use the CPU. You can run Setup again to retry.');
    Exit;
  end;
  if not DirExists(Staging + '\torch') or
     not DirExists(Staging + '\torchaudio') or
     not DirExists(Staging + '\torchcodec') then
  begin
    WarnCudaFailure(
      'CUDA unpack was incomplete (missing torch, torchaudio, or torchcodec ' +
      'in staging).' + #13#10#13#10 +
      'Stem splitting will use the CPU.');
    Exit;
  end;
  if not DirExists(InternalDir) then
  begin
    WarnCudaFailure(
      'Install folder is missing _internal; CUDA was not applied.' + #13#10 +
      'Expected: ' + InternalDir + #13#10#13#10 +
      'Stem splitting will use the CPU.');
    Exit;
  end;
  if not ReplaceCudaPackages(Staging, InternalDir) then
  begin
    WarnCudaFailure(
      'CUDA could not replace the CPU torch packages ' +
      '(check Setup log for details).' + #13#10#13#10 +
      'Stem splitting will use the CPU.');
    Exit;
  end;
  Log('CUDA extra installed under ' + InternalDir);
  if not WizardSilent then
    WizardForm.StatusLabel.Caption := 'CUDA toolkit installed.';
end;

procedure InitializeWizard;
begin
  NvidiaGpuDetected := HasNvidiaGpu;
  if NvidiaGpuDetected then
    Log('NVIDIA GPU detected; CUDA extra size label is ' + CudaDownloadSizeLabel)
  else
    Log('No NVIDIA GPU detected; CUDA extra page will be skipped');
  if CudaParamRequested then
    Log('/CUDA=1 set; CUDA extra will download even if the wizard page is skipped');
  CudaPage := CreateInputOptionPage(
    wpSelectTasks,
    'CUDA toolkit',
    'Optional download for faster stem splitting',
    CudaPromptText,
    True,
    False);
  CudaPage.Add('Yes');
  CudaPage.Add('No');
  CudaPage.SelectedValueIndex := CudaNoIndex;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = CudaPage.ID then
    Result := not NvidiaGpuDetected;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddAppToPath;
  if CurStep = ssPostInstall then
    MaybeInstallCudaExtra;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveAppFromPath;
end;
