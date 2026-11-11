@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   SEB Display Fix (Legacy Wrapper)
echo ========================================
echo.
echo [WARNING] Patching ONLY SafeExamBrowser.Monitoring.dll leaves
echo           SafeExamBrowser.Client.exe, SafeExamBrowser.exe,
echo           SafeExamBrowser.Configuration.dll, and
echo           SafeExamBrowser.UserInterface.Shared.dll UNPATCHED.
echo           This causes integrity/session-change lock screens and RDP failures.
echo.

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%_parse_args.cmd" %*
if errorlevel 1 exit /b 1

if "%DISPLAY_ONLY%"=="0" (
    echo [*] Delegating to scripts\patch_all.cmd for complete patching...
    echo     ^(Pass --display-only if you strictly want DisplayPatcher alone.^)
    echo.
    if "!NO_PAUSE!"=="1" (
        call "!SCRIPT_DIR!patch_all.cmd" --nopause "!SEB_DIR!"
    ) else (
        call "!SCRIPT_DIR!patch_all.cmd" "!SEB_DIR!"
    )
    exit /b !errorlevel!
)

:: --display-only path: run DisplayPatcher freshly against target DLL (never copy a stale DLL)
set "BIN_DIR=%SCRIPT_DIR%..\bin\final"
set "DISPLAY_PATCHER=%BIN_DIR%\DisplayPatcher.exe"
set "SEB_PATCHER=%BIN_DIR%\seb-patcher.exe"
set "OUTPUT_DLL=%BIN_DIR%\SafeExamBrowser.Monitoring.dll"
set "TARGET_DLL=%SEB_DIR%\SafeExamBrowser.Monitoring.dll"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator!
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

if not exist "%TARGET_DLL%" (
    echo [ERROR] Target DLL not found: %TARGET_DLL%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

if not exist "%DISPLAY_PATCHER%" (
    echo [ERROR] DisplayPatcher.exe not found at: %DISPLAY_PATCHER%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo [1/4] Stopping SEB processes...
taskkill /f /im SafeExamBrowser.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Client.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Service.exe >nul 2>&1
taskkill /f /im dnSpy.exe >nul 2>&1
net stop "SafeExamBrowser.Service" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Backing up Monitoring.dll...
if not exist "%TARGET_DLL%.bak" (
    copy "%TARGET_DLL%" "%TARGET_DLL%.bak" >nul
    echo     [OK] Backup created at %TARGET_DLL%.bak
) else (
    echo     [OK] Backup already exists
)

echo [3/4] Running DisplayPatcher.exe freshly on %TARGET_DLL%...
"%DISPLAY_PATCHER%" "%TARGET_DLL%" --in-place
set "DP_EXIT=%errorlevel%"
if %DP_EXIT% neq 0 (
    echo [ERROR] DisplayPatcher failed with exit code %DP_EXIT%!
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo [4/4] Checking companion binaries...
for %%F in (SafeExamBrowser.Client.exe SafeExamBrowser.exe SafeExamBrowser.Configuration.dll SafeExamBrowser.UserInterface.Shared.dll) do (
    if not exist "%SEB_DIR%\%%F.bak" (
        echo     [WARN] %%F has no .bak backup and may be unpatched! Run scripts\patch_all.cmd.
    )
)
if exist "%SEB_PATCHER%" "%SEB_PATCHER%" check "%SEB_DIR%"

if "%NO_PAUSE%"=="0" pause
exit /b 0
