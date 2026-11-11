@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   SEB BYPASS - ALL-IN-ONE PATCHER
echo ========================================
echo.

:: Capture script directory and parse arguments: patch_all.cmd [--nopause] [SEB_DIR]
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%_parse_args.cmd" %*
if errorlevel 1 exit /b 1

set "TARGET_DLL=%SEB_DIR%\SafeExamBrowser.Monitoring.dll"
set "BIN_DIR=%SCRIPT_DIR%..\bin\final"
set "SEB_PATCHER=%BIN_DIR%\seb-patcher.exe"
set "DISPLAY_PATCHER=%BIN_DIR%\DisplayPatcher.exe"
set "OUTPUT_DLL=%BIN_DIR%\SafeExamBrowser.Monitoring.dll"

:: Note if running inside a Windows RDP session
if defined SESSIONNAME (
    echo "%SESSIONNAME%" | findstr /i "RDP-" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Active Windows RDP session detected: %SESSIONNAME%
    )
)
echo [*] Target SEB directory: %SEB_DIR%
echo.

:: Check Admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator!
    call :maybe_pause
    exit /b 1
)

:: Check if SEB is installed
if not exist "%TARGET_DLL%" (
    echo [ERROR] SEB Monitoring DLL not found at:
    echo %TARGET_DLL%
    echo Is SEB installed?
    call :maybe_pause
    exit /b 1
)

:: Check companion SEB assemblies
for %%F in (
    SafeExamBrowser.Monitoring.dll
    SafeExamBrowser.Configuration.dll
    SafeExamBrowser.Client.exe
    SafeExamBrowser.exe
    SafeExamBrowser.UserInterface.Shared.dll
) do (
    if not exist "%SEB_DIR%\%%F" (
        echo [WARN] Companion binary missing: %SEB_DIR%\%%F
    )
)

:: Check if patchers exist
if not exist "%SEB_PATCHER%" (
    echo [ERROR] seb-patcher.exe not found at %SEB_PATCHER%
    call :maybe_pause
    exit /b 1
)
if not exist "%DISPLAY_PATCHER%" (
    echo [ERROR] DisplayPatcher.exe not found at %DISPLAY_PATCHER%
    call :maybe_pause
    exit /b 1
)

echo [1] Stopping SEB processes and SafeExamBrowser.Service...
taskkill /f /im SafeExamBrowser.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Client.exe >nul 2>&1
taskkill /f /im SafeExamBrowser.Service.exe >nul 2>&1
taskkill /f /im dnSpy.exe >nul 2>&1

sc query SafeExamBrowser.Service >nul 2>&1
if %errorlevel% equ 0 (
    net stop SafeExamBrowser.Service >nul 2>&1
    sc config SafeExamBrowser.Service start= disabled >nul 2>&1
    sc query SafeExamBrowser.Service | findstr /i "STOPPED" >nul 2>&1
    if !errorlevel! equ 0 (
        echo     [OK] SafeExamBrowser.Service stopped and disabled ^(prevents fDenyTSConnections=1 over RDP^).
    ) else (
        echo     [WARN] SafeExamBrowser.Service may still be running; check permissions if files are locked.
    )
) else (
    echo     [INFO] SafeExamBrowser.Service is not registered on this system.
)
timeout /t 2 /nobreak >nul
echo.

echo [2] Step 1: Running SEB IL Patcher (seb-patcher)...
echo ----------------------------------------
"%SEB_PATCHER%" patch "%SEB_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] seb-patcher failed!
    call :maybe_pause
    exit /b 1
)
echo ----------------------------------------
echo.

echo [3] Step 2: Running Display Patcher (DisplayPatcher --in-place)...
echo ----------------------------------------
"%DISPLAY_PATCHER%" "%TARGET_DLL%" --in-place
set "DP_EXIT=%errorlevel%"
if %DP_EXIT% neq 0 (
    echo [ERROR] DisplayPatcher failed with exit code %DP_EXIT%!
    call :maybe_pause
    exit /b 1
)
echo ----------------------------------------
echo.
echo [5] Verifying patches across all SEB assemblies...
echo ----------------------------------------
for %%F in (
    SafeExamBrowser.Monitoring.dll
    SafeExamBrowser.Configuration.dll
    SafeExamBrowser.Client.exe
    SafeExamBrowser.exe
    SafeExamBrowser.UserInterface.Shared.dll
    SafeExamBrowser.Lockdown.dll
) do (
    if exist "%SEB_DIR%\%%F" (
        for %%A in ("%SEB_DIR%\%%F") do set "FSIZE=%%~zA"
        if exist "%SEB_DIR%\%%F.bak" (
            echo     [OK] %%F ^(!FSIZE! bytes, backup: yes^)
        ) else (
            echo     [WARN] %%F ^(!FSIZE! bytes, backup: NO^)
        )
    )
)
echo.
"%SEB_PATCHER%" check "%SEB_DIR%"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FAILED - patch verification did not pass.
    call :maybe_pause
    exit /b 1
)

echo.
echo ========================================
echo   SUCCESS! ALL PATCHES APPLIED!
echo ========================================
echo You can now start Safe Exam Browser.

call :maybe_pause
exit /b 0

:maybe_pause
if "%NO_PAUSE%"=="0" pause
exit /b 0
