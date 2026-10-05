param()
$ErrorActionPreference = 'Stop'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaWeb = Join-Path $hinaRoot 'apps\web'
$hinaPreviousMode = $env:VITE_HINAA_AUTH_MODE
try {
    $env:VITE_HINAA_AUTH_MODE = 'clerk'
    Push-Location -LiteralPath $hinaWeb
    try {
        & node node_modules/typescript/bin/tsc -b
        if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed.' }
        & node node_modules/vite/bin/vite.js build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
    & node (Join-Path $PSScriptRoot 'prepare-live-build.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Production preparation failed.' }
} finally { $env:VITE_HINAA_AUTH_MODE = $hinaPreviousMode }
