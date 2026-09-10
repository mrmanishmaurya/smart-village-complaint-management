@echo off
TITLE Smart Village Complaint Management System - Local Server Mode
COLOR 0A

echo =======================================================
echo  Smart Village Complaint Management System
echo  LOCAL SERVER MODE LAUNCHER
echo =======================================================
echo.

cd /d "%~dp0"

REM Activate virtual environment if available
if exist "venv\Scripts\activate.bat" (
    echo Activating Python virtual environment...
    call venv\Scripts\activate.bat
)

echo Starting Local Server...
python start_local_server.py

pause
