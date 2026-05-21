@echo off
echo ========================================
echo   SEB Display Fix - Final Step
echo ========================================
echo.

:: Kill all SEB processes
echo [1/4] Killing SEB processes...
taskkill /f /im SafeExamBrowser.exe 2>nul
taskkill /f /im SafeExamBrowser.Service.exe 2>nul
taskkill /f /im dnSpy.exe 2>nul
net stop "SafeExamBrowser.Service" 2>nul
timeout /t 3 /nobreak >nul

:: Check if patched DLL exists in current directory
echo [2/4] Checking patched DLL...
set "PATCHED=%~dp0SafeExamBrowser.Monitoring.dll"
set "ORIGINAL=C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll"

if exist "%PATCHED%" (
    echo [OK] Found patched DLL at %PATCHED%
) else (
    echo.
    echo [ERROR] Patched DLL not found!
    echo Expected at: %PATCHED%
    echo.
    echo Please run DisplayPatcher.exe first!
    pause
    exit /b 1
)

:: Backup original
echo [3/4] Backing up original...
if not exist "%ORIGINAL%.bak" (
    copy "%ORIGINAL%" "%ORIGINAL%.bak" >nul
    echo [OK] Backup created at %ORIGINAL%.bak
) else (
    echo [OK] Backup already exists
)

:: Replace DLL
echo [4/4] Replacing DLL...
copy /y "%PATCHED%" "%ORIGINAL%" >nul
if %errorlevel%==0 (
    echo.
    echo ========================================
    echo   SUCCESS! DLL replaced!
    echo   You can now start SEB.
    echo ========================================
) else (
    echo.
    echo [ERROR] Failed to replace DLL!
    echo Make sure you run this as ADMINISTRATOR
    echo Make sure SEB is completely closed
)

echo.
pause
