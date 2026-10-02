@echo off
title HINA Intelligence OS - Web Server & Tunnel
echo ===================================================
echo   HINA Intelligence OS - Starting Web & Cloud Engine
echo ===================================================

cd /d "%~dp0"

:: 1. Check Python Backend
netstat -ano | findstr ":8000 " >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] Starting HINA Backend on port 8000...
    start /min "" "apps\api\.venv\Scripts\python.exe" -m uvicorn hinaa_api.main:app --host 127.0.0.1 --port 8000
    timeout /t 3 /nobreak >nul
) else (
    echo [1/3] HINA Backend is already running on http://127.0.0.1:8000
)

:: 2. Start Cloudflare Tunnel for remote/Vercel connectivity
echo [2/3] Checking Cloudflare Tunnel...
tasklist /fi "imagename eq cloudflared.exe" | findstr /i "cloudflared.exe" >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting Cloudflare Tunnel...
    start /min "" "cloudflared.exe" tunnel --url http://127.0.0.1:8000
) else (
    echo Cloudflare Tunnel is already active.
)

:: 3. Start Web Dev Server on localhost:5173
echo [3/3] Starting Vite Web Server on http://localhost:5173...
echo Opening browser in 3 seconds...
timeout /t 2 /nobreak >nul
start http://localhost:5173
call pnpm dev
