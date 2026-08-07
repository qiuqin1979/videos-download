@echo off
title Video Downloader
pushd "%~dp0"

echo ============================================
echo        Video Downloader - Quick Start
echo ============================================
echo.

REM --- Locate Python ---
echo [1/3] Locating Python ...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'python' not found on PATH.
    echo Trying 'py' launcher ...
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Neither 'python' nor 'py' found.
        echo Please install Python 3 from https://www.python.org/downloads/
        pause
        popd
        exit /b 1
    )
    set "PYCMD=py"
) else (
    set "PYCMD=python"
)
echo Using: %PYCMD%
%PYCMD% --version
echo.

REM --- Install / update dependencies (use TUNA mirror by default for CN networks) ---
echo [2/3] Checking dependencies ...
%PYCMD% -m pip install -U -r requirements.txt --timeout 30 -i https://pypi.tuna.tsinghua.edu.cn/simple -q
if %errorlevel% neq 0 (
    echo [WARN] TUNA mirror failed, trying default PyPI ...
    %PYCMD% -m pip install -U -r requirements.txt --timeout 30 -q
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Check your network.
        pause
        popd
        exit /b 1
    )
)
echo Dependencies OK.
echo.

REM --- Launch ---
echo [3/3] Starting Video Downloader ...
echo.
%PYCMD% video_download.py
set "RC=%errorlevel%"
echo.
echo ============================================
echo Program exited with code %RC%
echo ============================================
pause
popd
