@echo off
echo ===================================================
echo   Creating Desktop Shortcut: Smart Village Management
echo ===================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
pause
