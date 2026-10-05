@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-live.ps1"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-live.ps1" -Public -Deploy
exit /b %ERRORLEVEL%
