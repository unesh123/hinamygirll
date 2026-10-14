# scripts/show-status.ps1
$ErrorActionPreference = 'SilentlyContinue'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaRuntime = Join-Path $hinaRoot '.runtime\live'
$stateFile = Join-Path $hinaRuntime 'runner-state.json'

Write-Host '======================================================================' -ForegroundColor Magenta
Write-Host '  HINAA AI COMPANION - LIVE STATUS' -ForegroundColor Magenta
Write-Host '======================================================================' -ForegroundColor Magenta

# 1. State from runner
$state = $null
if (Test-Path $stateFile) {
    try { $state = Get-Content $stateFile -Raw | ConvertFrom-Json } catch {}
}

# 2. Local Backend Health Check
$apiOk = $false
try {
    $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($res.status -eq 'ok' -or $res.service -eq 'hinaa-api') { $apiOk = $true }
} catch {}

# 3. Local Web Health Check
$webOk = $false
try {
    $res = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($res.StatusCode -eq 200) { $webOk = $true }
} catch {}

# 4. Live Vercel Health Check
$liveOk = $false
try {
    $res = Invoke-RestMethod -Uri 'https://hinaa-workspace.vercel.app/health/live' -TimeoutSec 4 -UseBasicParsing -ErrorAction Stop
    if ($res.status -eq 'ok' -or $res.service -eq 'hinaa-api') { $liveOk = $true }
} catch {}

# 5. Authenticated loopback desktop bridge check. The token is never printed.
$desktopOk = $false
$desktopTokenPath = Join-Path $hinaRoot '.runtime\desktop\bridge.token'
if (Test-Path -LiteralPath $desktopTokenPath) {
    try {
        $desktopToken = (Get-Content -LiteralPath $desktopTokenPath -Raw).Trim()
        if ($desktopToken.Length -ge 32) {
            $desktopRes = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -Headers @{ Authorization = "Bearer $desktopToken" } -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($desktopRes.status -eq 'ready') { $desktopOk = $true }
        }
    } catch {}
}

# Display Statuses
if ($liveOk) {
    Write-Host '  [Online Site]    ' -NoNewline
    Write-Host 'ONLINE (200 OK)' -ForegroundColor Green -NoNewline
    Write-Host ' -> https://hinaa-workspace.vercel.app'
} else {
    Write-Host '  [Online Site]    ' -NoNewline
    Write-Host 'CONNECTING / OFFLINE' -ForegroundColor Yellow -NoNewline
    Write-Host ' -> https://hinaa-workspace.vercel.app'
}

if ($apiOk) {
    Write-Host '  [Local Backend]  ' -NoNewline
    Write-Host 'ACTIVE (Port 8000)' -ForegroundColor Green -NoNewline
    Write-Host ' -> http://127.0.0.1:8000/health/live'
} else {
    Write-Host '  [Local Backend]  ' -NoNewline
    Write-Host 'STOPPED' -ForegroundColor Red
}

if ($webOk) {
    Write-Host '  [Local Frontend] ' -NoNewline
    Write-Host 'ACTIVE (Port 5173)' -ForegroundColor Green -NoNewline
    Write-Host ' -> http://127.0.0.1:5173'
} else {
    Write-Host '  [Local Frontend] ' -NoNewline
    Write-Host 'STOPPED' -ForegroundColor Red
}

Write-Host '  [Desktop Hands]  ' -NoNewline
if ($desktopOk) {
    Write-Host 'ACTIVE (paired loopback bridge)' -ForegroundColor Green
} else {
    Write-Host 'OFFLINE' -ForegroundColor Red
}

if ($state -and $state.tunnelOrigin) {
    Write-Host '  [Cloudflare]     ' -NoNewline
    Write-Host $state.tunnelOrigin -ForegroundColor Cyan
}

Write-Host '  [Voice Engine]   ' -NoNewline
Write-Host 'ElevenLabs Creator (Aisha: WUgmmuDCpFXQ4z0NUUYX)' -ForegroundColor Magenta

if ($state -and $state.runnerPid) {
    $rProc = Get-Process -Id $state.runnerPid -ErrorAction SilentlyContinue
    if ($rProc) {
        Write-Host '  [Runner PID]     ' -NoNewline
        Write-Host ($state.runnerPid.ToString() + ' (Active)') -ForegroundColor Gray
    }
}

Write-Host '======================================================================' -ForegroundColor Magenta
