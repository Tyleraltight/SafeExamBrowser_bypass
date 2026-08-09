@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   SEB BYPASS - ALL-IN-ONE PATCHER
echo ========================================
echo.

:: Define paths
set "SEB_DIR=C:\Program Files\SafeExamBrowser\Application"
set "TARGET_DLL=%SEB_DIR%\SafeExamBrowser.Monitoring.dll"
set "BIN_DIR=%~dp0..\bin\final"
set "SEB_PATCHER=%BIN_DIR%\seb-patcher.exe"
set "DISPLAY_PATCHER=%BIN_DIR%\DisplayPatcher.exe"
set "OUTPUT_DLL=%BIN_DIR%\SafeExamBrowser.Monitoring.dll"

:: Check Admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script must be run as Administrator!
    pause
    exit /b 1
)

:: Check if SEB is installed
if not exist "%TARGET_DLL%" (
    echo [ERROR] SEB Monitoring DLL not found at:
    echo %TARGET_DLL%
    echo Is SEB installed?
    pause
    exit /b 1
)

:: Check if patchers exist
if not exist "%SEB_PATCHER%" (
    echo [ERROR] seb-patcher.exe not found at %SEB_PATCHER%
    pause
    exit /b 1
)
if not exist "%DISPLAY_PATCHER%" (
    echo [ERROR] DisplayPatcher.exe not found at %DISPLAY_PATCHER%
    pause
    exit /b 1
)

echo [1] Killing SEB processes and services...
taskkill /f /im SafeExamBrowser.exe 2>nul
taskkill /f /im SafeExamBrowser.Client.exe 2>nul
taskkill /f /im SafeExamBrowser.Service.exe 2>nul
taskkill /f /im dnSpy.exe 2>nul
net stop SafeExamBrowser.Service >nul 2>&1
timeout /t 2 /nobreak >nul
echo.

echo [2] Step 1: Running VM Detection Patcher (seb-patcher)...
echo ----------------------------------------
"%SEB_PATCHER%" patch "%SEB_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] seb-patcher failed!
    pause
    exit /b 1
)
echo ----------------------------------------
echo.

echo [3] Step 2: Running Display Patcher...
echo ----------------------------------------
:: Run DisplayPatcher in its directory so it outputs there
cd /d "%BIN_DIR%"
"%DISPLAY_PATCHER%"
if %errorlevel% neq 0 (
    echo [ERROR] DisplayPatcher failed!
    pause
    exit /b 1
)
echo ----------------------------------------
echo.

echo [4] Step 3: Deploying final double-patched DLL...
:: The DisplayPatcher created the final DLL in its own directory
if not exist "%OUTPUT_DLL%" (
    echo [ERROR] DisplayPatcher did not generate the patched DLL!
    pause
    exit /b 1
)

echo Copying patched DLL to SEB folder...
copy /y "%OUTPUT_DLL%" "%TARGET_DLL%"
if %errorlevel% neq 0 (
    echo [!] Standard copy failed, trying PowerShell...
    powershell -Command "Copy-Item '%OUTPUT_DLL%' '%TARGET_DLL%' -Force"
)

echo.
echo [5] Verifying patch...
"%SEB_PATCHER%" check "%SEB_DIR%"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FAILED - patch verification did not pass.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   SUCCESS! ALL PATCHES APPLIED!
echo ========================================
echo You can now start Safe Exam Browser.

pause
exit /b 0
