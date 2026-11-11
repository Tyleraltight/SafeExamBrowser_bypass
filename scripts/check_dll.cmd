@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   SEB ASSEMBLY ^& SERVICE DIAGNOSTIC
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%_parse_args.cmd" %*
if errorlevel 1 exit /b 1

set "BIN_DIR=%SCRIPT_DIR%..\bin\final"
set "SEB_PATCHER=%BIN_DIR%\seb-patcher.exe"
set "STAGED_DLL=%BIN_DIR%\SafeExamBrowser.Monitoring.dll"

echo [*] Target SEB directory: %SEB_DIR%
if not exist "%SEB_DIR%" (
    echo [ERROR] SEB directory not found: %SEB_DIR%
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
)

echo.
echo [1] Target SEB assemblies and backups:
set "MISSING_BACKUPS=0"
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
            for %%B in ("%SEB_DIR%\%%F.bak") do set "BSIZE=%%~zB"
            echo     [OK] %%F : !FSIZE! bytes ^(backup: !BSIZE! bytes^)
        ) else (
            echo     [WARN] %%F : !FSIZE! bytes ^(NO .bak backup^)
            if /i not "%%F"=="SafeExamBrowser.Lockdown.dll" set /a MISSING_BACKUPS+=1
        )
    ) else (
        if /i not "%%F"=="SafeExamBrowser.Lockdown.dll" (
            echo     [MISS] %%F : NOT FOUND
        )
    )
)

echo.
echo [2] SafeExamBrowser.Service status:
sc query SafeExamBrowser.Service >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=3,4" %%S in ('sc query SafeExamBrowser.Service ^| findstr /i "STATE"') do (
        echo     Service state: %%S %%T
    )
    sc qc SafeExamBrowser.Service | findstr /i "START_TYPE"
) else (
    echo     SafeExamBrowser.Service is not registered.
)

echo.
echo [3] Staged Monitoring DLL in bin\final (for reference only):
if exist "%STAGED_DLL%" (
    for %%A in ("%STAGED_DLL%") do echo     Found: %%~zA bytes ^(modified %%~tA^)
    echo     Note: Do NOT copy this alone; use scripts\patch_all.cmd to patch all binaries.
) else (
    echo     Not present at %STAGED_DLL%
)

echo.
echo [4] Running seb-patcher.exe check:
set "CHK_RC=0"
if exist "%SEB_PATCHER%" (
    "%SEB_PATCHER%" check "%SEB_DIR%"
    set "CHK_RC=!errorlevel!"
) else (
    echo     [WARN] seb-patcher.exe not found at %SEB_PATCHER%
    set "CHK_RC=1"
)

echo.
echo ========================================
if %MISSING_BACKUPS% gtr 0 (
    echo [WARN] Some core binaries have no .bak backup. Run scripts\patch_all.cmd as Admin.
) else (
    echo Check complete.
)
echo ========================================

if "%NO_PAUSE%"=="0" pause
exit /b %CHK_RC%
