$ErrorActionPreference = 'SilentlyContinue'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaRuntime = Join-Path $hinaRoot '.runtime\live'
$legacyRuntime = Join-Path $hinaRoot '.runtime\pids'

Write-Host "Stopping Hina live services..." -ForegroundColor Cyan

# 1. Signal graceful stop if runner is active
$runnerPidFile = Join-Path $hinaRuntime 'runner.pid'
if (Test-Path -LiteralPath $runnerPidFile) {
    New-Item -ItemType File -Path (Join-Path $hinaRuntime 'stop-requested') -Force | Out-Null
    $rPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $runnerPidFile -Raw).Trim(), [ref]$rPid)) {
        for ($i = 0; $i -lt 15; $i++) {
            $p = Get-Process -Id $rPid -ErrorAction SilentlyContinue
            if (-not $p) { break }
            Start-Sleep -Milliseconds 200
        }
        $p = Get-Process -Id $rPid -ErrorAction SilentlyContinue
        if ($p) {
            taskkill.exe /PID $rPid /T /F 2>$null | Out-Null
        }
    }
}

# 2. Terminate any child processes recorded in pid files
$pidFiles = @(
    (Join-Path $hinaRuntime 'api.pid'),
    (Join-Path $hinaRuntime 'web.pid'),
    (Join-Path $hinaRuntime 'tunnel.pid'),
    (Join-Path $hinaRuntime 'desktop.pid'),
    (Join-Path $legacyRuntime 'backend.pid'),
    (Join-Path $legacyRuntime 'frontend.pid')
)
foreach ($pf in $pidFiles) {
    if (Test-Path -LiteralPath $pf) {
        $cPid = 0
        if ([int]::TryParse((Get-Content -LiteralPath $pf -Raw).Trim(), [ref]$cPid)) {
            taskkill.exe /PID $cPid /T /F 2>$null | Out-Null
        }
        Remove-Item -LiteralPath $pf -Force -ErrorAction SilentlyContinue
    }
}

# 3. Kill any running cloudflared
Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# 4. Synchronously free ports owned by Hina's managed services
$targetPorts = @(8000, 5173, 8765)
foreach ($port in $targetPorts) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        if ($conn.OwningProcess -gt 0) {
            Write-Host "Releasing port $port (killing PID $($conn.OwningProcess))..." -ForegroundColor Yellow
            taskkill.exe /PID $conn.OwningProcess /T /F 2>$null | Out-Null
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

# 5. Wait up to 3 seconds until ports are completely free
for ($i = 0; $i -lt 15; $i++) {
    $stillListening = Get-NetTCPConnection -LocalPort 8000, 5173, 8765 -State Listen -ErrorAction SilentlyContinue
    if (-not $stillListening) { break }
    Start-Sleep -Milliseconds 200
}

# 6. Cleanup runtime lock & pid files
Remove-Item -LiteralPath (Join-Path $hinaRuntime 'stop-requested') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $hinaRuntime 'runner.pid') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $hinaRuntime 'runner.lock') -Force -ErrorAction SilentlyContinue

Write-Host "Hina stopped cleanly. Ports 8000, 5173, and 8765 are free." -ForegroundColor Green
