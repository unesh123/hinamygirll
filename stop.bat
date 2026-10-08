@echo off
setlocal
title HINAA — Stopping Services
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-live.ps1"
echo.
echo [Hina] All services stopped. Press any key to close this window...
pause >nul
exit /b 0
