@echo off
title Fresher Job Finder Server
cd /d "%~dp0"

echo =====================================================================
echo   Data Analyst Job Finder & ATS Resume Tailoring Server
echo   Directory: %~dp0
echo =====================================================================
echo.
echo [1/2] Opening browser to http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"

echo [2/2] Starting Uvicorn Python Server...
echo (Keep this window open while using the website)
echo.
python start.py

if errorlevel 1 (
    echo.
    echo =====================================================================
    echo [ERROR] Server exited. Check if Python is installed or port 8000 is in use.
    echo =====================================================================
    pause
)

