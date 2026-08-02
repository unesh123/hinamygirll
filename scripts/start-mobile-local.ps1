param(
    [switch]$Lan,
    [switch]$Https,
    [string]$BindHost = "127.0.0.1",
    [string]$LanOrigin,
    [string]$CertPath,
    [string]$KeyPath,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo "apps\api\.venv\Scripts\python.exe"
$pnpm = (Get-Command pnpm -ErrorAction Stop).Source
$runtime = Join-Path $repo ".runtime"
$web = Join-Path $repo "apps\web"

function Stop-HinaaLocal {
    foreach ($name in @("api.pid", "web.pid")) {
        $pidFile = Join-Path $runtime $name
        if (Test-Path -LiteralPath $pidFile) {
            $procId = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
            if ($procId) {
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            }
            Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Output "Stopped local HINAA API/web processes recorded in .runtime (if any)."
    Write-Output "If ports remain occupied, close the owning process manually in Task Manager."
}

if ($Stop) {
    Stop-HinaaLocal
    return
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend venv missing. Create apps/api/.venv and install requirements-dev.txt"
}
if (-not (Test-Path -LiteralPath (Join-Path $web "node_modules"))) {
    throw "Frontend deps missing. Run: pnpm --dir apps/web install --frozen-lockfile"
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$apiHost = $BindHost
if ($Lan) {
    if ($env:HINAA_LAN_BIND_HOST) {
        $apiHost = $env:HINAA_LAN_BIND_HOST
    } else {
        $apiHost = "0.0.0.0"
    }
    Write-Warning "LAN bind is OPT-IN. This is developer exposure on your trusted local network, not production security."
}

if ($Https) {
    if (-not $CertPath) { $CertPath = Join-Path $repo ".cert\hinaa-dev.pem" }
    if (-not $KeyPath) { $KeyPath = Join-Path $repo ".cert\hinaa-dev-key.pem" }
    $CertPath = [IO.Path]::GetFullPath($CertPath)
    $KeyPath = [IO.Path]::GetFullPath($KeyPath)
    if (-not (Test-Path -LiteralPath $CertPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
        throw "Trusted cert files missing. Create/trust manually (do not silent-install root CA). Expected: $CertPath and $KeyPath"
    }
    $env:HINAA_DEV_CERT_PATH = $CertPath
    $env:HINAA_DEV_KEY_PATH = $KeyPath
}

# Never print secret values — only presence.
$envLocal = Join-Path $repo "apps\api\.env.local"
$providerNames = @("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION", "GEMINI_API_KEY", "GEMINI_MODEL")
$providerStatus = @()
if (Test-Path -LiteralPath $envLocal) {
    $raw = Get-Content -LiteralPath $envLocal -ErrorAction SilentlyContinue
    foreach ($name in $providerNames) {
        $hit = $raw | Where-Object { $_ -match "^\s*$name\s*=" }
        if ($hit) { $providerStatus += "$name=PRESENT" } else { $providerStatus += "$name=MISSING" }
    }
} else {
    $providerStatus = @("apps/api/.env.local=MISSING")
}

$detectedLan = $env:HINAA_LAN_IP
if (-not $detectedLan) {
    $detectedLan = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.AddressState -eq "Preferred" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Select-Object -First 1 -ExpandProperty IPAddress
}

if ($Lan -and $detectedLan) {
    $schemeHint = if ($Https) { "https" } else { "http" }
    $wsHint = if ($Https) { "wss" } else { "ws" }
    $origin = if ($LanOrigin) { $LanOrigin } else { "$schemeHint`://$detectedLan`:5173" }
    if (-not $env:HINAA_ALLOWED_ORIGINS) {
        $env:HINAA_ALLOWED_ORIGINS = "http://127.0.0.1:5173,http://localhost:5173,$origin"
        Write-Output "CORS origins (configured for this process only): $($env:HINAA_ALLOWED_ORIGINS)"
    }
    Write-Output "Expected mobile page: $origin"
    Write-Output "WebSocket scheme when page is HTTPS must be $wsHint"
} else {
    Write-Output "Loopback-only bind. Set -Lan and/or HINAA_LAN_IP for phone testing."
}

# Port checks
foreach ($port in @(8000, 5173)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        Write-Output "Port $port already listening (PID $($listener.OwningProcess))"
    }
}

$apiReady = $false
try {
    $health = Invoke-RestMethod "http://127.0.0.1:8000/health/live" -TimeoutSec 2
    $apiReady = $health.status -eq "ok"
} catch {}

if (-not $apiReady) {
    $api = Start-Process -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "hinaa_api.main:app", "--app-dir", "apps/api", "--host", $apiHost, "--port", "8000") `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime "api.stdout.log") `
        -RedirectStandardError (Join-Path $runtime "api.stderr.log")
    Set-Content -LiteralPath (Join-Path $runtime "api.pid") -Value $api.Id
    Start-Sleep -Seconds 1
}

$webReady = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if (-not $webReady) {
    $webHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
    $webArgs = @("--dir", "apps/web", "dev", "--host", $webHost, "--port", "5173")
    if ($Https -and $env:HINAA_DEV_CERT_PATH -and $env:HINAA_DEV_KEY_PATH) {
        # Vite HTTPS requires plugin/config; expose cert env for documented manual trust path.
        $env:VITE_DEV_HTTPS = "1"
    }
    $webProcess = Start-Process -FilePath $pnpm `
        -ArgumentList $webArgs `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime "web.stdout.log") `
        -RedirectStandardError (Join-Path $runtime "web.stderr.log")
    Set-Content -LiteralPath (Join-Path $runtime "web.pid") -Value $webProcess.Id
}

$scheme = if ($Https) { "https" } else { "http" }
Write-Output ""
Write-Output "=== HINAA mobile-local (developer) ==="
Write-Output "API health: http://127.0.0.1:8000/health/live"
Write-Output "PC app: $scheme`://127.0.0.1:5173/"
if ($Lan -and $detectedLan) {
    Write-Output "Phone app (sanitized): $scheme`://$detectedLan`:5173/"
}
Write-Output "Provider status (names only): $($providerStatus -join ', ')"
Write-Output "HTTPS requested: $Https"
Write-Output "Auth mode note: HINAA_AUTH_MODE=dev is NOT production OIDC."
Write-Output "Firewall: allow inbound TCP 5173/8000 only on trusted private LAN profiles if needed."
Write-Output "Do not expose database ports. Do not use public tunnels automatically."
Write-Output "Stop: powershell -File scripts/start-mobile-local.ps1 -Stop"
Write-Output "=============================="
