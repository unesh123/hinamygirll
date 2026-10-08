# scripts/live-console.ps1
$ErrorActionPreference = 'SilentlyContinue'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaRuntime = Join-Path $hinaRoot '.runtime\live'
$stateFile = Join-Path $hinaRuntime 'runner-state.json'
$runnerPidFile = Join-Path $hinaRuntime 'runner.pid'

function Clear-ScreenSafe {
    try { [Console]::Clear() } catch { Clear-Host }
}

function Test-RunnerActive {
    if (Test-Path -LiteralPath $runnerPidFile) {
        $rPid = 0
        if ([int]::TryParse((Get-Content -LiteralPath $runnerPidFile -Raw).Trim(), [ref]$rPid)) {
            $p = Get-Process -Id $rPid -ErrorAction SilentlyContinue
            if ($p -and $p.ProcessName -eq 'python') { return $rPid }
        }
    }
    return 0
}

function Start-Services {
    Write-Host ''
    Write-Host '  [Hina] Starting live runner in background (-Public -Deploy)...' -ForegroundColor Cyan
    $startScript = Join-Path $PSScriptRoot 'start-live.ps1'
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startScript -Public -Deploy
}

function Stop-Services {
    Write-Host ''
    Write-Host '  [Hina] Stopping all services...' -ForegroundColor Yellow
    $stopScript = Join-Path $PSScriptRoot 'stop-live.ps1'
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopScript
}

function Render-Dashboard {
    Clear-ScreenSafe
    Write-Host '======================================================================' -ForegroundColor Magenta
    Write-Host '  HINAA AI COMPANION - LIVE RUNNER AND SUPERVISOR' -ForegroundColor Magenta
    Write-Host '======================================================================' -ForegroundColor Magenta

    $runnerPid = Test-RunnerActive

    # Check local backend (8000)
    $apiOk = $false
    try {
        $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($res.status -eq 'ok' -or $res.service -eq 'hinaa-api') { $apiOk = $true }
    } catch {}

    # Check local web (5173)
    $webOk = $false
    try {
        $res = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) { $webOk = $true }
    } catch {}

    # Check online live (Vercel)
    $liveOk = $false
    try {
        $res = Invoke-RestMethod -Uri 'https://hinaa-workspace.vercel.app/health/live' -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($res.status -eq 'ok' -or $res.service -eq 'hinaa-api') { $liveOk = $true }
    } catch {}

    # State file
    $state = $null
    if (Test-Path $stateFile) {
        try { $state = Get-Content $stateFile -Raw | ConvertFrom-Json } catch {}
    }

    # Summary Badge
    Write-Host '  [Overall Status] ' -NoNewline
    if ($liveOk) {
        Write-Host 'ONLINE (Healthy)' -ForegroundColor Green
    } elseif ($apiOk -and $webOk) {
        Write-Host 'LOCAL READY (Connecting to Vercel...)' -ForegroundColor Yellow
    } elseif ($runnerPid -gt 0) {
        Write-Host 'STARTING UP...' -ForegroundColor Yellow
    } else {
        Write-Host 'STOPPED' -ForegroundColor Red
    }

    Write-Host '----------------------------------------------------------------------' -ForegroundColor DarkGray

    # Online Vercel URL
    Write-Host '  [Online Site]    ' -NoNewline
    if ($liveOk) {
        Write-Host 'https://hinaa-workspace.vercel.app' -ForegroundColor Green -NoNewline
        Write-Host ' (200 OK)' -ForegroundColor DarkGreen
    } else {
        Write-Host 'https://hinaa-workspace.vercel.app' -ForegroundColor DarkGray -NoNewline
        Write-Host ' (Waiting for tunnel sync)' -ForegroundColor DarkYellow
    }

    # Local Web URL
    Write-Host '  [Local Web]      ' -NoNewline
    if ($webOk) {
        Write-Host 'http://127.0.0.1:5173' -ForegroundColor Green
    } else {
        Write-Host 'http://127.0.0.1:5173' -ForegroundColor DarkGray
    }

    # Local API URL
    Write-Host '  [Local API]      ' -NoNewline
    if ($apiOk) {
        Write-Host 'http://127.0.0.1:8000/health/live' -ForegroundColor Green
    } else {
        Write-Host 'http://127.0.0.1:8000' -ForegroundColor DarkGray
    }

    # Tunnel URL
    if ($state -and $state.tunnelOrigin) {
        Write-Host '  [Cloudflare]     ' -NoNewline
        Write-Host $state.tunnelOrigin -ForegroundColor Cyan
    }

    # Voice Info
    Write-Host '  [Voice Engine]   ' -NoNewline
    Write-Host 'ElevenLabs (Aisha / Sweet Girlfriend: WUgmmuDCpFXQ4z0NUUYX)' -ForegroundColor Magenta

    # Supervisor PID
    if ($runnerPid -gt 0) {
        Write-Host '  [Live Runner]    ' -NoNewline
        Write-Host ($runnerPid.ToString() + ' (Active)') -ForegroundColor Gray
    }

    Write-Host '======================================================================' -ForegroundColor Magenta
    Write-Host '  CONTROLS:' -ForegroundColor White
    Write-Host '   [R] ' -NoNewline -ForegroundColor Yellow; Write-Host 'Restart all services'
    Write-Host '   [S] ' -NoNewline -ForegroundColor Red; Write-Host 'Stop all services'
    Write-Host '   [O] ' -NoNewline -ForegroundColor Green; Write-Host 'Open Online site (Vercel) in browser'
    Write-Host '   [L] ' -NoNewline -ForegroundColor Cyan; Write-Host 'Open Local preview (5173) in browser'
    Write-Host '   [T] ' -NoNewline -ForegroundColor Magenta; Write-Host 'Show recent runner logs'
    Write-Host '   [Q] ' -NoNewline -ForegroundColor Gray; Write-Host 'Quit console (runner keeps running in background)'
    Write-Host '======================================================================' -ForegroundColor Magenta
    Write-Host '  Auto-refreshing every 5 seconds... Press any hotkey above:' -ForegroundColor DarkGray
}

# Ensure runner is running on start
$runnerPid = Test-RunnerActive
if ($runnerPid -eq 0) {
    Start-Services
    Write-Host '  Waiting for services to spin up...' -ForegroundColor Yellow
    for ($i = 0; $i -lt 6; $i++) {
        Start-Sleep -Seconds 1
        $apiUp = $false
        try {
            $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/live' -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
            if ($r.status -eq 'ok') { $apiUp = $true; break }
        } catch {}
        if ($apiUp) { break }
    }
}

# Main Supervisor Console Loop
$lastRender = 0
while ($true) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ($now - $lastRender -ge 5) {
        Render-Dashboard
        $lastRender = $now
    }

    if ([Console]::KeyAvailable) {
        $rawKey = [Console]::ReadKey($true)
        $key = $rawKey.KeyChar.ToString().ToUpper()
        if ($key -eq 'R') {
            Stop-Services
            Start-Sleep -Seconds 1
            Start-Services
            $lastRender = 0
        } elseif ($key -eq 'S') {
            Stop-Services
            $lastRender = 0
        } elseif ($key -eq 'O') {
            Start-Process 'https://hinaa-workspace.vercel.app'
        } elseif ($key -eq 'L') {
            Start-Process 'http://127.0.0.1:5173'
        } elseif ($key -eq 'T') {
            Clear-ScreenSafe
            Write-Host '=== RECENT RUNNER LOGS ===' -ForegroundColor Cyan
            $outLog = Join-Path $hinaRuntime 'runner.out.log'
            $errLog = Join-Path $hinaRuntime 'runner.err.log'
            if (Test-Path $outLog) {
                Write-Host ''
                Write-Host '--- stdout (last 15 lines) ---' -ForegroundColor Green
                Get-Content $outLog -Tail 15
            }
            if (Test-Path $errLog) {
                Write-Host ''
                Write-Host '--- stderr (last 15 lines) ---' -ForegroundColor Red
                Get-Content $errLog -Tail 15
            }
            Write-Host ''
            Write-Host 'Press any key to return to dashboard...' -ForegroundColor Yellow
            [Console]::ReadKey($true) | Out-Null
            $lastRender = 0
        } elseif ($key -eq 'Q') {
            Write-Host ''
            Write-Host '[Hina] Exiting supervisor console.' -ForegroundColor Gray
            Write-Host '[Hina] Background runner is still active. To stop, run stop.bat' -ForegroundColor Cyan
            Start-Sleep -Milliseconds 800
            exit 0
        }
    }

    Start-Sleep -Milliseconds 250
}
