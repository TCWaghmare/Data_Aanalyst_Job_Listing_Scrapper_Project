@echo off
title Stop Job Finder Server
echo Stopping any running Job Finder Server / Python processes on port 8000...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    echo Terminating process PID %%a listening on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo Job Finder server stopped.
