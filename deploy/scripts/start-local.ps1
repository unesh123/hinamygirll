<#
.SYNOPSIS
    HINAA OS - Phase 17 Local-First Hardened Desktop Launcher
.DESCRIPTION
    Runs the HINAA backend with SQLite WAL durability, non-blocking probes,
    and verified local isolation.
#>

param(
    [string]$Profile = "LOCAL_DESKTOP",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " HINAA OS - Starting in profile: $Profile" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$env:HINAA_DEPLOYMENT_PROFILE = $Profile
$env:HINAA_BIND_PORT = $Port
$env:PYTHONPATH = "apps/api"

# Healthcheck loop
Write-Host "[HINAA] Starting API server..." -ForegroundColor Green
& "apps\api\.venv\Scripts\python.exe" -m uvicorn hinaa_api.main:app --host 127.0.0.1 --port $Port
