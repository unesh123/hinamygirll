@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-live.ps1" -Dev
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo HINAA failed to start. Exit code: %EXIT_CODE%
  pause
)
exit /b %EXIT_CODE%
