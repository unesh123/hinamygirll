# Restores the public API path for the local backend.
#
# The backend runs on 127.0.0.1:8000 and the deployed frontend reaches it only
# through the same-origin rewrites in vercel.json, so the app is down whenever
# this tunnel is down. Two things keep biting us, and both are handled here:
#
#   1. Quick tunnels hand out a new hostname every start, so vercel.json has to
#      be rewritten and the frontend redeployed each time.
#   2. This network passes the QUIC precheck but then times out dialling the
#      edge addresses, leaving cloudflared retrying forever and the hostname
#      returning Cloudflare error 530. Forcing --protocol http2 avoids it.
#
# Usage:
#   powershell -File scripts\tunnel.ps1            # restart, repoint, report
#   powershell -File scripts\tunnel.ps1 -Deploy    # ...and ship the new rewrite
param(
    [switch]$Deploy,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root 'tunnel.log'
$out = Join-Path $root 'tunnel.out.log'
$err = Join-Path $root 'tunnel.err.log'
$exe = Join-Path $root 'cloudflared.exe'

Write-Host "Stopping any running cloudflared..."
Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Remove-Item $log, $out, $err -Force -ErrorAction SilentlyContinue

Write-Host "Starting quick tunnel -> http://127.0.0.1:$Port (http2)..."
# The child's own --logfile never appeared on one run while the identical
# command registered fine with its output redirected, so redirect here: the
# hostname is only ever printed to the standard streams.
Start-Process -FilePath $exe -ArgumentList @(
    'tunnel', '--url', "http://127.0.0.1:$Port",
    '--no-autoupdate', '--protocol', 'http2'
) -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err

$hostName = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    foreach ($file in @($log, $out, $err)) {
        if (-not (Test-Path $file)) { continue }
        $match = Select-String -Path $file -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' |
            Select-Object -First 1
        if ($match) { $hostName = $match.Matches[0].Value; break }
    }
    if ($hostName) { break }
}

if (-not $hostName) {
    Write-Error "No hostname appeared after 60s. Read $out and $err for the failure."
    exit 1
}
Write-Host "Tunnel hostname: $hostName"

Write-Host "Checking the tunnel actually reaches the backend..."
try {
    $probe = Invoke-WebRequest -Uri "$hostName/health" -Headers @{ 'bypass-tunnel-reminder' = 'true' } -TimeoutSec 30 -UseBasicParsing
    if ($probe.StatusCode -ne 200) { throw "HTTP $($probe.StatusCode)" }
    Write-Host "  /health -> $($probe.Content)"
} catch {
    Write-Error "Tunnel is up but $hostName/health failed: $_. Nothing was changed."
    exit 1
}

$vercelJson = Join-Path $root 'vercel.json'
$text = Get-Content $vercelJson -Raw
$new = $text -replace 'https://[a-z0-9-]+\.trycloudflare\.com', $hostName
if ($new -ne $text) {
    Set-Content -Path $vercelJson -Value $new -NoNewline
    Write-Host "vercel.json rewrites repointed."
} else {
    Write-Host "vercel.json already points here."
}

if ($Deploy) {
    Write-Host "Deploying to production..."
    Push-Location $root
    try { npx vercel deploy --prod --yes } finally { Pop-Location }
    Write-Host "Verify with: curl https://hinaa-workspace.vercel.app/api/v1/providers"
} else {
    Write-Host "Next: redeploy for the new rewrite to take effect,"
    Write-Host "      or rerun with -Deploy."
}
