$ErrorActionPreference = 'Stop'
$hinaRuntime = Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime\live'
if (Test-Path -LiteralPath (Join-Path $hinaRuntime 'runner.pid')) {
    New-Item -ItemType File -Path (Join-Path $hinaRuntime 'stop-requested') -Force | Out-Null
    Write-Output 'Graceful stop requested. The runner will stop its own services on the next health check.'
} else {
    Write-Output 'The live runner is not active.'
}
