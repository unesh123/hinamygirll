param()
# ErrorActionPreference left at Continue so Vite's chunk-size warnings written
# to stderr do not trigger a false fatal exit. We gate on $LASTEXITCODE only.
$ErrorActionPreference = 'Continue'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaWeb = Join-Path $hinaRoot 'apps\web'
$hinaPreviousMode = $env:VITE_HINAA_AUTH_MODE
try {
    $env:VITE_HINAA_AUTH_MODE = 'clerk'
    Push-Location -LiteralPath $hinaWeb
    try {
        # Merge stderr into stdout so warnings print but don't trigger Stop.
        & node node_modules/typescript/bin/tsc -b 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed (exit $LASTEXITCODE)." }
        & node node_modules/vite/bin/vite.js build 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
    & node (Join-Path $PSScriptRoot 'prepare-live-build.mjs') 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Production preparation failed (exit $LASTEXITCODE)." }
} finally { $env:VITE_HINAA_AUTH_MODE = $hinaPreviousMode }
Write-Output 'Build complete.'

