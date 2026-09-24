# scripts/update-tunnel.ps1 — One command to (re)publish HINAA to the live site.
# Quick tunnels get a NEW URL every restart; this script starts one, rewrites
# vercel.json with the fresh URL, and (optionally) deploys to Vercel.
# Usage: powershell -File scripts\update-tunnel.ps1 [-Deploy]
param(
    [switch]$Deploy
)
$ErrorActionPreference = 'Stop'
$rootDir = Join-Path $PSScriptRoot '..'
$logDir  = Join-Path $rootDir '.runtime\logs'
$pidDir  = Join-Path $rootDir '.runtime\pids'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Force -Path $pidDir | Out-Null }

Write-Host '=== HINAA live publisher ===' -ForegroundColor Magenta

# 1. Backend must be healthy first.
$backendOk = $false
try {
    $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -Method Get -TimeoutSec 3 -ErrorAction Stop
    if ($res.status -eq 'ok') { $backendOk = $true }
} catch { }
if (-not $backendOk) {
    Write-Host 'Backend is not healthy on :8000 — run start.bat first.' -ForegroundColor Red
    exit 1
}
Write-Host '[1/3] Backend healthy.' -ForegroundColor Green

# 2. Stop any previous quick tunnel, then start a fresh one.
$old = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($old) { $old | Stop-Process -Force; Start-Sleep -Seconds 1 }
$cloudflared = Join-Path $rootDir 'cloudflared.exe'
$tunnelLog = Join-Path $logDir 'tunnel.log'
$tunnelErr = Join-Path $logDir 'tunnel.err.log'
Start-Process -FilePath $cloudflared `
    -ArgumentList 'tunnel', '--url', 'http://127.0.0.1:8000', '--no-autoupdate' `
    -WorkingDirectory $rootDir `
    -RedirectStandardOutput $tunnelLog -RedirectStandardError $tunnelErr `
    -WindowStyle Hidden
$tunnelUrl = $null
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $match = Select-String -Path @($tunnelLog, $tunnelErr) -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($match) { $tunnelUrl = $match.Matches[0].Value; break }
}
if (-not $tunnelUrl) {
    Write-Host 'Tunnel did not report a URL within 20s. Check .runtime\logs\tunnel.err.log' -ForegroundColor Red
    exit 1
}
$host_ = ([uri]$tunnelUrl).Host
Write-Host "[2/3] Tunnel up: $tunnelUrl" -ForegroundColor Green

# 3. Rewrite vercel.json rewrites with the fresh host.
#    Text substitution, not ConvertFrom-Json/ConvertTo-Json: re-serializing
#    reformats the whole file on every rotation, burying the 3-line change that
#    is the only real edit.
$vercelJson = Join-Path $rootDir 'vercel.json'
$raw = Get-Content $vercelJson -Raw
$bomless = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($vercelJson, ($raw -replace 'https://[a-z0-9-]+\.trycloudflare\.com', $tunnelUrl), $bomless)
Write-Host '[3/3] vercel.json now points at the live tunnel.' -ForegroundColor Green

if ($Deploy) {
    Write-Host 'Deploying to Vercel (production)...' -ForegroundColor Cyan
    Push-Location $rootDir
    # .vercel/project.json carries an orgId this token cannot deploy to; the
    # project lives in the personal scope, so name it.
    npx vercel deploy --prod --yes --scope uneshs-projects
    Pop-Location
    Write-Host "Live site is now wired to $tunnelUrl" -ForegroundColor Magenta
} else {
    Write-Host "Next: commit vercel.json and run  powershell -File scripts\update-tunnel.ps1 -Deploy  to publish." -ForegroundColor Yellow
}
