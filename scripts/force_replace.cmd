@echo off
echo ========================================
echo   FORCE DLL REPLACE
echo ========================================
echo.

set "PATCHED=%~dp0bin\final\SafeExamBrowser.Monitoring.dll"
set "TARGET=C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll"

if not exist "%PATCHED%" (
    echo [ERROR] Patched DLL not found at %PATCHED%
    pause
    exit /b 1
)

echo [OK] Patched DLL found
echo [1] Killing SEB...
taskkill /f /im SafeExamBrowser.exe 2>nul
taskkill /f /im SafeExamBrowser.Service.exe 2>nul
taskkill /f /im dnSpy.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2] Backing up...
if not exist "%TARGET%.bak" copy "%TARGET%" "%TARGET%.bak" >nul 2>&1

echo [3] Replacing DLL...
copy /y "%PATCHED%" "%TARGET%"
if %errorlevel% neq 0 (
    echo [!] Copy failed, trying PowerShell...
    powershell -Command "Copy-Item '%PATCHED%' '%TARGET%' -Force"
)

echo.
echo [4] Checking result...
for %%A in ("%TARGET%") do set NEW=%%~zA
for %%A in ("%PATCHED%") do set PAT=%%~zA
echo     Patched: %PAT% bytes
echo     Result:  %NEW% bytes
if "%NEW%"=="%PAT%" (
    echo.
    echo SUCCESS! DLL replaced! Start SEB now.
) else (
    echo.
    echo FAILED - file was not replaced.
)
pause
