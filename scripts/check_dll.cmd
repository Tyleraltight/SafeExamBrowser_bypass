@echo off
echo ========================================
echo   DLL DIAGNOSTIC CHECK
echo ========================================
echo.

echo [1] Patched DLL (shared folder):
set "PATCHED=%~dp0SafeExamBrowser.Monitoring.dll"
if exist "%PATCHED%" (
    for %%A in ("%PATCHED%") do echo     FOUND: %%~zA bytes
    echo     Path: %PATCHED%
) else (
    echo     NOT FOUND at %PATCHED%
    echo.
    echo [!] The patcher did NOT save the patched DLL here!
    echo [!] You need to run DisplayPatcher.exe first.
    echo [!] Run it FROM this shared folder directory.
    pause
    exit /b 1
)

echo.
echo [2] Original DLL (SEB directory):
set "TARGET=C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll"
for %%A in ("%TARGET%") do echo     Size: %%~zA bytes

echo.
echo [3] Backup DLL:
set "BAK=%TARGET%.bak"
if exist "%BAK%" (
    for %%A in ("%BAK%") do echo     Size: %%~zA bytes
) else (
    echo     No backup found
)

echo.
echo [4] Patched DLL from previous runs:
set "PATCHED2=C:\Program Files\SafeExamBrowser\Application\SafeExamBrowser.Monitoring.dll.patched"
if exist "%PATCHED2%" (
    for %%A in ("%PATCHED2%") do echo     Found at SEB dir: %%~zA bytes
) else (
    echo     Not found in SEB directory
)

echo.
echo ========================================
if exist "%PATCHED%" (
    echo Ready to replace. Run force_replace.cmd as Admin!
) else (
    echo NOT ready. Run DisplayPatcher.exe first!
)
echo ========================================
pause
