@echo off
title HINA Intelligence OS - Native PC Desktop
echo ===================================================
echo   HINA Intelligence OS - Starting Native PC App
echo ===================================================

cd /d "%~dp0"

:: 1. Check if backend is running on port 8000
netstat -ano | findstr ":8000 " >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] Starting HINA Cognitive Python Backend on port 8000...
    start /min "" "apps\api\.venv\Scripts\python.exe" -m uvicorn hinaa_api.main:app --host 127.0.0.1 --port 8000
    timeout /t 3 /nobreak >nul
) else (
    echo [1/3] HINA Backend is already running on http://127.0.0.1:8000
)

:: 2. Check if web build exists
if not exist "apps\web\dist\index.html" (
    echo [2/3] Building Web Frontend assets...
    call pnpm build
) else (
    echo [2/3] Web Frontend build verified.
)

:: 3. Launch Native Electron PC App
echo [3/3] Launching HINA Native PC Desktop App...
call pnpm desktop:start
