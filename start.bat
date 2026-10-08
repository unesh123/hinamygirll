@echo off
setlocal
title HINAA — AI Companion Live Runner
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\live-console.ps1"
if errorlevel 1 (
  echo.
  echo [Hina] Console exited with code %ERRORLEVEL%.
  pause
)
