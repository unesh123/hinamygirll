@echo off
setlocal
title HINAA — Restarting Services
cd /d "%~dp0"
echo.
echo ======================================================================
echo   [Hina] Restarting Live Services...
echo ======================================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-live.ps1"
timeout /t 2 /nobreak >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-live.ps1" -Public -Deploy
echo.
echo [Hina] Services restarted. Opening status console...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\live-console.ps1"
