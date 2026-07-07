@echo off
chcp 65001 > NUL
title Antigravity Youtube Downloader
echo ===================================================
echo  Starting Antigravity Youtube Downloader...
echo ===================================================
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start the application.
    echo Please ensure Python and dependencies are installed.
    echo Run: pip install -r requirements.txt
    echo.
    pause
)
