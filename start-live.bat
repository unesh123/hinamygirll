@echo off
setlocal
cd /d "%~dp0"

echo [Hina] Building authenticated frontend...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-live.ps1"
if errorlevel 1 (
    echo.
    echo [Hina] Build step failed. See output above.
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo [Hina] Starting live runner (API + tunnel)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-live.ps1" -Public -Deploy
if errorlevel 1 (
    echo.
    echo [Hina] Runner failed to start. Check .runtime\live\runner.err.log
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo.
echo [Hina] Live. Local: http://127.0.0.1:5173
echo Press any key to close this window (runner keeps going in background).
pause >nul
exit /b 0
