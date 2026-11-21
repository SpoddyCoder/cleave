@echo off
rem Back up every Cleave user folder to a dated folder on the Desktop, then
rem delete the originals so the next install starts from a clean slate.
rem
rem Folders (see cleave/paths.py and cleave/user_config.py):
rem   Data      Documents\Cleave, or %CLEAVE_DATA% when set
rem             (projects, presets, textures, themes, models, cleave.db)
rem   Settings  %APPDATA%\Cleave (config.yaml, crash log)
rem   Local     %LOCALAPPDATA%\Cleave (CUDA download, several GB)
rem
rem The installed program under Program Files is left alone.
rem Nothing is deleted unless every backup copy succeeds.

setlocal EnableExtensions DisableDelayedExpansion

tasklist /FI "IMAGENAME eq cleave.exe" 2>nul | find /I "cleave.exe" >nul
if not errorlevel 1 (
    echo Cleave is running. Close it and run this script again.
    goto :fail
)

rem Known folders can be redirected (OneDrive), so ask Windows for them.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"`) do set "DOCS=%%P"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%P"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "STAMP=%%P"

if not defined DOCS set "DOCS=%USERPROFILE%\Documents"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
if not defined STAMP (
    echo Could not read the date and time.
    goto :fail
)

rem Without these, the folders below would resolve to \Cleave on the
rem current drive, which is not Cleave's.
if not defined APPDATA goto :no_appdata
if not defined LOCALAPPDATA goto :no_appdata

set "DATA_DIR=%DOCS%\Cleave"
if defined CLEAVE_DATA set "DATA_DIR=%CLEAVE_DATA%"
set "SETTINGS_DIR=%APPDATA%\Cleave"
set "LOCAL_DIR=%LOCALAPPDATA%\Cleave"
set "BACKUP=%DESKTOP%\Cleave-backup-%STAMP%"

call :guard "%DATA_DIR%" || goto :fail
call :guard "%SETTINGS_DIR%" || goto :fail
call :guard "%LOCAL_DIR%" || goto :fail

echo.
echo Cleave folders found:
set "FOUND="
call :show "%DATA_DIR%"
call :show "%SETTINGS_DIR%"
call :show "%LOCAL_DIR%"
if not defined FOUND (
    echo   none. Nothing to back up or delete.
    goto :done
)
echo.
echo Backup to: %BACKUP%
echo.
choice /C YN /M "Back up these folders, then DELETE them"
if errorlevel 2 (
    echo Cancelled. Nothing changed.
    goto :done
)

mkdir "%BACKUP%" || goto :fail

call :backup "%DATA_DIR%" "Data" || goto :backup_failed
call :backup "%SETTINGS_DIR%" "Settings" || goto :backup_failed
call :backup "%LOCAL_DIR%" "Local" || goto :backup_failed

echo.
echo Backup complete. Deleting originals...
set "LEFT="
call :remove "%DATA_DIR%"
call :remove "%SETTINGS_DIR%"
call :remove "%LOCAL_DIR%"
if defined LEFT (
    echo.
    echo Some folders could not be fully deleted. Close anything using them
    echo and delete them by hand. The backup is complete.
    goto :fail
)

echo.
echo Done. Backup: %BACKUP%
if not defined CLEAVE_DATA goto :done
echo Note: CLEAVE_DATA is still set to %CLEAVE_DATA%
echo Remove it from your environment variables to use Documents\Cleave.
goto :done

rem ---------------------------------------------------------------------------

:show
rem No ( ) blocks around paths: a ")" in a path would end the block early.
if not exist "%~1\" exit /b 0
echo   %~1
set "FOUND=1"
exit /b 0

:backup
rem %1 source folder, %2 name of the copy under the backup folder.
if not exist "%~1\" exit /b 0
echo.
echo Copying %~1
robocopy "%~1" "%BACKUP%\%~2" /E /COPY:DAT /DCOPY:T /R:1 /W:1 /NFL /NDL /NP /NJH
rem robocopy exit codes 0-7 mean success; 8 and above mean a copy failed.
if errorlevel 8 exit /b 1
exit /b 0

:remove
if not exist "%~1\" exit /b 0
echo   %~1
rmdir /S /Q "%~1"
if exist "%~1\" set "LEFT=1"
exit /b 0

:guard
rem Refuse a folder whose deletion would take far more than Cleave's data:
rem a drive root, or a known folder such as the profile or Documents.
rem CLEAVE_DATA is the usual way to get here.
set "GUARD=%~f1"
if "%GUARD:~-1%"=="\" set "GUARD=%GUARD:~0,-1%"
if "%~pnx1"=="\" goto :guard_refuse
call :guard_known "%USERPROFILE%" || goto :guard_refuse
call :guard_known "%DOCS%" || goto :guard_refuse
call :guard_known "%DESKTOP%" || goto :guard_refuse
call :guard_known "%APPDATA%" || goto :guard_refuse
call :guard_known "%LOCALAPPDATA%" || goto :guard_refuse
call :guard_known "%SystemRoot%" || goto :guard_refuse
exit /b 0

:guard_known
rem %1 a known folder. Fails when it is the folder :guard is checking.
rem An empty %1 would expand to the current folder, so skip it.
if "%~1"=="" exit /b 0
set "KNOWN=%~f1"
if "%KNOWN:~-1%"=="\" set "KNOWN=%KNOWN:~0,-1%"
if /I "%GUARD%"=="%KNOWN%" exit /b 1
exit /b 0

:guard_refuse
echo Refusing to delete %GUARD%.
echo Check CLEAVE_DATA in your environment variables.
exit /b 1

:no_appdata
echo APPDATA or LOCALAPPDATA is not set, so the Cleave folders cannot be found.
goto :fail

:backup_failed
echo.
echo A backup copy failed. Nothing was deleted.
echo Partial backup: %BACKUP%
goto :fail

:fail
echo.
pause
endlocal
exit /b 1

:done
echo.
pause
endlocal
exit /b 0
