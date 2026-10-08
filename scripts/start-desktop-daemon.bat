@echo off
title HINAA Autonomous Desktop Control Daemon
cd /d "%~dp0\.."
echo ===============================================================
echo   Starting HINAA Autonomous Desktop Control Daemon...
echo   Physical Mouse Movement, Clicks, Screen Capture and Keystrokes
echo ===============================================================

if exist "apps\api\.venv\Scripts\python.exe" (
    "apps\api\.venv\Scripts\python.exe" "scripts\hinaa_desktop_daemon.py"
) else (
    python "scripts\hinaa_desktop_daemon.py"
)
pause
