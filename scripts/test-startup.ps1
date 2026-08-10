# scripts/test-startup.ps1
$ErrorActionPreference = "Stop"

$rootDir = Join-Path $PSScriptRoot ".."

Write-Host "Running launcher tests..." -ForegroundColor Cyan

# 1. Check required files
$requiredFiles = @(
    "start.bat",
    "stop.bat",
    "scripts\start-hinaa.ps1",
    "scripts\stop-hinaa.ps1",
    "apps\api\.env.local",
    "apps\web\package.json",
    "apps\api\.venv\Scripts\python.exe"
)

foreach ($file in $requiredFiles) {
    $path = Join-Path $rootDir $file
    if (-not (Test-Path $path)) {
        Write-Host "FAIL: Missing required file: $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "PASS: All required files exist." -ForegroundColor Green

# 2. Check PowerShell parsing
$scripts = @(
    "scripts\start-hinaa.ps1",
    "scripts\stop-hinaa.ps1"
)

foreach ($script in $scripts) {
    $path = Join-Path $rootDir $script
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$errors) | Out-Null
    if ($errors.Count -gt 0) {
        Write-Host "FAIL: PowerShell syntax error in $script" -ForegroundColor Red
        exit 1
    }
}
Write-Host "PASS: All PowerShell scripts parse correctly." -ForegroundColor Green

Write-Host "All startup tests passed." -ForegroundColor Green
exit 0
