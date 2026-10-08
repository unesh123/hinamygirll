# PowerShell launcher for HINAA Autonomous Desktop Control Daemon
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "  Starting HINAA Autonomous Desktop Control Daemon (Port 8765)..." -ForegroundColor Green
Write-Host "  Enables physical mouse movement, clicking, and desktop capture" -ForegroundColor Yellow
Write-Host "===============================================================" -ForegroundColor Cyan

$pythonExe = Join-Path $root "apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$daemonScript = Join-Path $root "scripts\hinaa_desktop_daemon.py"
& $pythonExe $daemonScript
