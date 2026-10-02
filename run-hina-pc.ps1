# HINA Intelligence OS - PowerShell Launcher for Native PC Desktop
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Magenta
Write-Host "   HINA Intelligence OS - Native PC Desktop" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Magenta

# 1. Verify Backend on Port 8000
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if (-not $conn) {
    Write-Host "[1/3] Starting HINA Cognitive Python Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
    $env:PYTHONPATH = "apps/api"
    Start-Process -FilePath "apps\api\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn hinaa_api.main:app --host 127.0.0.1 --port 8000" -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "[1/3] HINA Backend is active on http://127.0.0.1:8000" -ForegroundColor Green
}

# 2. Check Web Build
if (-not (Test-Path "apps/web/dist/index.html")) {
    Write-Host "[2/3] Building frontend assets..." -ForegroundColor Yellow
    pnpm build
} else {
    Write-Host "[2/3] Frontend build ready." -ForegroundColor Green
}

# 3. Start Native PC Desktop App
Write-Host "[3/3] Launching HINA Native PC Desktop App (Electron)..." -ForegroundColor Cyan
pnpm desktop:start
