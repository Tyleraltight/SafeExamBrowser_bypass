@echo off
:: Shared argument parser for SEB batch scripts.
:: Must be invoked via `call "%~dp0_parse_args.cmd" %*` inside a `setlocal enabledelayedexpansion` block.
set "NO_PAUSE=0"
if "%SEB_NOPAUSE%"=="1" set "NO_PAUSE=1"
set "DISPLAY_ONLY=0"
set "ALLOW_FORCE=0"
set "SEB_DIR=C:\Program Files\SafeExamBrowser\Application"

:_pa_loop
if "%~1"=="" exit /b 0
set "_PA_ARG=%~1"
if /i "%~1"=="--nopause" (
    set "NO_PAUSE=1"
) else if /i "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
) else if /i "%~1"=="--display-only" (
    set "DISPLAY_ONLY=1"
) else if /i "%~1"=="--force-monitoring-only" (
    set "ALLOW_FORCE=1"
) else if "!_PA_ARG:~0,1!"=="-" (
    echo [ERROR] Unknown option: %~1
    exit /b 1
) else (
    set "SEB_DIR=%~1"
)
shift /1
goto _pa_loop
