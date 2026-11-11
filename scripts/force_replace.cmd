@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   FORCE DLL REPLACE (DEPRECATED)
echo ========================================
echo.
echo [WARNING] Copying bin\final\SafeExamBrowser.Monitoring.dll directly:
echo   1. May overwrite SEB with a STALE prebuilt DLL from an older build.
echo   2. Leaves SafeExamBrowser.exe, SafeExamBrowser.Client.exe,
echo      SafeExamBrowser.Configuration.dll, and
echo      SafeExamBrowser.UserInterface.Shared.dll UNPATCHED.
echo   3. Unpatched Client.exe / SafeExamBrowser.exe cause integrity errors,
echo      session-change red lock screens, and black/broken RDP windows.
echo.
echo Recommended command: scripts\patch_all.cmd
echo.

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%_parse_args.cmd" %*
if errorlevel 1 exit /b 1

if "%ALLOW_FORCE%"=="0" (
    echo [ABORTED] Refusing to blindly overwrite Monitoring.dll alone.
    echo           Run scripts\patch_all.cmd as Administrator instead, or pass
    echo           --force-monitoring-only if you intentionally want this override.
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

set "PATCHED=%SCRIPT_DIR%..\bin\final\SafeExamBrowser.Monitoring.dll"
set "TARGET=%SEB_DIR%\SafeExamBrowser.Monitoring.dll"

if not exist "%PATCHED%" (
    echo [ERROR] Patched DLL not found at %PATCHED%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)
if not exist "%TARGET%" (
    echo [ERROR] Target SEB DLL not found at %TARGET%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

for %%A in ("%PATCHED%") do echo [INFO] Source DLL: %%~zA bytes, modified %%~tA
echo [1] Stopping SEB processes and service...
taskkill /f /im SafeExamBrowser.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Client.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Service.exe >nul 2>&1
taskkill /f /im dnSpy.exe >nul 2>&1
net stop SafeExamBrowser.Service >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2] Backing up...
if not exist "%TARGET%.bak" copy "%TARGET%" "%TARGET%.bak" >nul 2>&1

echo [3] Replacing Monitoring.dll...
copy /y "%PATCHED%" "%TARGET%"
if %errorlevel% neq 0 (
    echo [!] Copy failed, trying PowerShell...
    powershell -NoProfile -Command "Copy-Item -LiteralPath '%PATCHED%' -Destination '%TARGET%' -Force"
)

echo.
echo [4] Checking result...
for %%A in ("%TARGET%") do set "NEW=%%~zA"
for %%A in ("%PATCHED%") do set "PAT=%%~zA"
echo     Patched: %PAT% bytes
echo     Result:  %NEW% bytes
if "%NEW%"=="%PAT%" (
    echo.
    echo [OK] Monitoring.dll replaced.
    echo [REMINDER] Run scripts\patch_all.cmd to ensure Client.exe, SafeExamBrowser.exe,
    echo            Configuration.dll, and UserInterface.Shared.dll are also patched!
) else (
    echo.
    echo [ERROR] FAILED - file was not replaced.
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)
if "%NO_PAUSE%"=="0" pause
exit /b 0
