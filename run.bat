@echo off
chcp 65001 > NUL
title Antigravity Youtube Downloader

echo ===================================================
echo  Starting Antigravity Youtube Downloader...
echo ===================================================

:: 기본값 설정
set PYTHON_CMD=python

:: 사용자 프로필의 아나콘다 및 일반 파이썬 설치 경로 감지
if exist "%USERPROFILE%\anaconda3\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\anaconda3\python.exe"
) else if exist "%USERPROFILE%\miniconda3\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\miniconda3\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD="%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe"
)

%PYTHON_CMD% main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start the application.
    echo Please ensure Python and dependencies are installed.
    echo Run: pip install -r requirements.txt
    echo.
    pause
)
