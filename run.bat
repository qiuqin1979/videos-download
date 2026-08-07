@echo off
title Video Downloader
cd /d "%~dp0"

echo ============================================
echo        Video Downloader - Setup & Run
echo ============================================
echo.

REM Check if yt-dlp is installed
pip show yt-dlp >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing yt-dlp ...
    pip install yt-dlp -y
    echo.
)

echo Starting Video Downloader...
echo.
python video_download.py

pause
