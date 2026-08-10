# scripts/start-hinaa.ps1
$ErrorActionPreference = 'Stop'

$rootDir = Join-Path $PSScriptRoot '..'
$logDir = Join-Path $rootDir '.runtime\logs'
$pidDir = Join-Path $rootDir '.runtime\pids'

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Force -Path $pidDir | Out-Null }

Write-Host '==================================================' -ForegroundColor Magenta
Write-Host ' HINAA — Local Development Launcher' -ForegroundColor Magenta
Write-Host '==================================================' -ForegroundColor Magenta
Write-Host ''

Write-Host '[1/5] Checking environment...' -ForegroundColor Cyan

$pythonPath = Join-Path $rootDir 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path $pythonPath)) {
    Write-Host 'ERROR: Python virtual environment not found at apps\api\.venv' -ForegroundColor Red
    Write-Host 'Run: cd apps\api ; python -m venv .venv ; .venv\Scripts\activate ; pip install -r requirements.txt'
    exit 1
}
Write-Host '      Python: OK'

if (-not (Get-Command 'node' -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: Node.js is not installed or not in PATH.' -ForegroundColor Red
    exit 1
}
Write-Host '      Node:   OK'

if (-not (Get-Command 'pnpm' -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: pnpm is not installed. Install via: npm install -g pnpm' -ForegroundColor Red
    exit 1
}
Write-Host '      pnpm:   OK'

if (-not (Test-Path (Join-Path $rootDir 'apps\api\.env.local'))) {
    Write-Host 'ERROR: apps\api\.env.local not found.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '[2/5] Checking ports...' -ForegroundColor Cyan

function Check-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connection) { return $true }
    return $false
}

$backendPort = 8000
$frontendPort = 5173

if (Check-Port $backendPort) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health/live" -Method Get -TimeoutSec 2 -ErrorAction Stop
        Write-Host "      $backendPort : Already serving HINAA backend (Healthy)" -ForegroundColor Green
        $global:backendAlreadyRunning = $true
    } catch {
        Write-Host "ERROR: Port $backendPort is occupied by an unknown process." -ForegroundColor Red
        Write-Host "Please stop the process on port $backendPort and try again."
        exit 1
    }
} else {
    Write-Host "      $backendPort : available"
    $global:backendAlreadyRunning = $false
}

if (Check-Port $frontendPort) {
    Write-Host "      $frontendPort : Already serving an application." -ForegroundColor Yellow
    Write-Host 'Assuming it is the HINAA frontend.'
    $global:frontendAlreadyRunning = $true
} else {
    Write-Host "      $frontendPort : available"
    $global:frontendAlreadyRunning = $false
}


Write-Host ''
Write-Host '[3/5] Starting backend...' -ForegroundColor Cyan

# Durable local memory: learned facts survive restarts via file-backed SQLite.
$env:HINAA_DATABASE_URL = "sqlite+pysqlite:///./.runtime/hinaa.db"

if (-not $global:backendAlreadyRunning) {
    $backendLog = Join-Path $logDir 'backend.log'
    $backendErr = Join-Path $logDir 'backend.err'
    $backendArgs = "-m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port $backendPort"
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList $backendArgs -WorkingDirectory $rootDir -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
    $backendProcess.Id | Out-File (Join-Path $pidDir 'backend.pid') -Encoding utf8
    
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($backendProcess.HasExited) {
            Write-Host 'ERROR: Backend process crashed immediately. Check .runtime/logs/backend.log' -ForegroundColor Red
            exit 1
        }
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health/live" -Method Get -ErrorAction Stop
            if ($response.status -eq 'ok') {
                $healthy = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 1
    }

    if (-not $healthy) {
        Write-Host 'ERROR: Backend failed to become healthy within 30 seconds.' -ForegroundColor Red
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        exit 1
    }
}
Write-Host "      Healthy: http://127.0.0.1:$backendPort/health/live" -ForegroundColor Green

Write-Host ''
Write-Host '[4/5] Starting frontend...' -ForegroundColor Cyan

if (-not $global:frontendAlreadyRunning) {
    $frontendLog = Join-Path $logDir 'frontend.log'
    $frontendErr = Join-Path $logDir 'frontend.err'
    $frontendArgs = "/c pnpm run --dir apps/web dev --host 127.0.0.1 --port $frontendPort"
    $frontendProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList $frontendArgs -WorkingDirectory $rootDir -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
    $frontendProcess.Id | Out-File (Join-Path $pidDir 'frontend.pid') -Encoding utf8
    
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($frontendProcess.HasExited) {
            Write-Host 'ERROR: Frontend process crashed immediately. Check .runtime/logs/frontend.log' -ForegroundColor Red
            exit 1
        }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort/" -Method Get -UseBasicParsing -ErrorAction Stop
            $ready = $true
            break
        } catch { }
        Start-Sleep -Seconds 1
    }

    if (-not $ready) {
        Write-Host 'ERROR: Frontend failed to start within 30 seconds.' -ForegroundColor Red
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
        exit 1
    }
}
Write-Host "      Ready: http://127.0.0.1:$frontendPort/" -ForegroundColor Green

Write-Host ''
Write-Host '[5/5] Opening HINAA...' -ForegroundColor Cyan

Start-Process "http://127.0.0.1:$frontendPort/"

Write-Host ''
Write-Host 'HINAA is running.' -ForegroundColor Magenta
Write-Host 'Frontend: http://127.0.0.1:5173/'
Write-Host 'Backend:  http://127.0.0.1:8000/'
Write-Host 'Logs:     .runtime/logs/'
Write-Host ''
Write-Host 'To stop safely, run stop.bat or scripts/stop-hinaa.ps1' -ForegroundColor Yellow
