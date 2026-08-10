# scripts/stop-hinaa.ps1
$ErrorActionPreference = 'Stop'

$runtimeDir = Join-Path $PSScriptRoot '..\.runtime\pids'

function Stop-HinaaProcess {
    param([string]$Name)
    $pidFile = Join-Path $runtimeDir "$Name.pid"
    if (Test-Path $pidFile) {
        $processId = Get-Content $pidFile
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Stopping $Name (PID $processId)..." -ForegroundColor Cyan
            Stop-Process -Id $processId -Force
            Write-Host "$Name stopped successfully." -ForegroundColor Green
        } else {
            Write-Host "$Name (PID $processId) is not running." -ForegroundColor Yellow
        }
        Remove-Item $pidFile -Force
    } else {
        Write-Host "No PID file found for $Name. It may not be running." -ForegroundColor DarkGray
    }
}

Write-Host '==================================================' -ForegroundColor Magenta
Write-Host ' HINAA — Stopping Local Instances' -ForegroundColor Magenta
Write-Host '==================================================' -ForegroundColor Magenta

Stop-HinaaProcess -Name 'frontend'
Stop-HinaaProcess -Name 'backend'

Write-Host 'Done.'
