@echo off
title Antigravity Youtube Downloader
echo ===================================================
echo  Antigravity Youtube Downloader를 실행하는 중...
echo ===================================================
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [오류] 프로그램 실행에 실패했습니다.
    echo Python 및 필수 패키지(customtkinter, yt-dlp, pillow)가 올바르게 설치되었는지 확인하세요.
    echo 패키지를 설치하려면 'pip install -r requirements.txt'를 실행하세요.
    echo.
    pause
)
