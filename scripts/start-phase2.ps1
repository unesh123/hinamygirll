param(
    [switch]$Https,
    [string]$CertPath,
    [string]$KeyPath
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo 'apps\api\.venv\Scripts\python.exe'
$pnpm = (Get-Command pnpm -ErrorAction Stop).Source
$web = Join-Path $repo 'apps\web'
$runtime = Join-Path $repo '.runtime'
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.AddressState -eq 'Preferred' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -First 1 -ExpandProperty IPAddress)

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Backend environment missing. Run: python -m venv apps/api/.venv; apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt'
}
if (-not (Test-Path -LiteralPath (Join-Path $web 'node_modules'))) {
    throw 'Frontend dependencies missing. Run: pnpm --dir apps/web install --frozen-lockfile'
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$apiReady = $false
try {
    $apiReady = (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/health/live' -TimeoutSec 2).StatusCode -eq 200
} catch {}
if (-not $apiReady) {
    $api = Start-Process -FilePath $python `
        -ArgumentList @('-m','uvicorn','hinaa_api.main:app','--app-dir','apps/api','--host','127.0.0.1','--port','8000') `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime 'api.stdout.log') `
        -RedirectStandardError (Join-Path $runtime 'api.stderr.log')
    Set-Content -LiteralPath (Join-Path $runtime 'api.pid') -Value $api.Id
}

if ($Https) {
    if (-not $CertPath) { $CertPath = Join-Path $repo '.cert\hinaa-dev.pem' }
    if (-not $KeyPath) { $KeyPath = Join-Path $repo '.cert\hinaa-dev-key.pem' }
    $CertPath = [IO.Path]::GetFullPath($CertPath)
    $KeyPath = [IO.Path]::GetFullPath($KeyPath)
    if (-not (Test-Path -LiteralPath $CertPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
        throw "Trusted certificate files are missing. See docs/24-phase-2-review.md. Expected: $CertPath and $KeyPath"
    }
    $env:HINAA_DEV_CERT_PATH = $CertPath
    $env:HINAA_DEV_KEY_PATH = $KeyPath
}

$webReady = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if (-not $webReady) {
    $webProcess = Start-Process -FilePath $pnpm `
        -ArgumentList @('--dir','apps/web','dev','--host','0.0.0.0','--port','5173') `
        -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime 'web.stdout.log') `
        -RedirectStandardError (Join-Path $runtime 'web.stderr.log')
    Set-Content -LiteralPath (Join-Path $runtime 'web.pid') -Value $webProcess.Id
}

$scheme = if ($Https) { 'https' } else { 'http' }
Write-Output "API health: http://127.0.0.1:8000/health/live"
Write-Output "PC app: $scheme`://127.0.0.1:5173/"
if ($lanIp) { Write-Output "Android app: $scheme`://$lanIp`:5173/" }
if (-not $Https) { Write-Warning 'Android microphone capture requires a trusted HTTPS origin. HTTP is suitable for mock/text review only.' }
