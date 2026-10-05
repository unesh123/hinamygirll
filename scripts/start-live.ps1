param([switch]$Public, [switch]$Deploy, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaRuntime = Join-Path $hinaRoot '.runtime\live'
New-Item -ItemType Directory -Path $hinaRuntime -Force | Out-Null
$hinaPidFile = Join-Path $hinaRuntime 'runner.pid'
if (Test-Path -LiteralPath $hinaPidFile) {
    $hinaExistingPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $hinaPidFile -Raw).Trim(), [ref]$hinaExistingPid)) {
        $hinaExisting = Get-Process -Id $hinaExistingPid -ErrorAction SilentlyContinue
        if ($hinaExisting -and $hinaExisting.ProcessName -eq 'python') {
            Write-Output 'Hina live runner is already active. Stop it before changing profiles.'
            return
        }
    }
}
$hinaPython = Join-Path $hinaRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $hinaPython)) { throw 'Hina Python environment is missing.' }
$hinaArguments = @('"' + (Join-Path $PSScriptRoot 'live_runner.py') + '"')
if ($Public) { $hinaArguments += '--public' }
if ($Deploy) { $hinaArguments += '--deploy' }
if ($Dev) { $hinaArguments += '--dev' }
$hinaStopFile = Join-Path $hinaRuntime 'stop-requested'
if (Test-Path -LiteralPath $hinaStopFile) { Remove-Item -LiteralPath $hinaStopFile -Force }
$hinaProcess = Start-Process -FilePath $hinaPython -ArgumentList $hinaArguments -WorkingDirectory $hinaRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hinaRuntime 'runner.out.log') -RedirectStandardError (Join-Path $hinaRuntime 'runner.err.log') -PassThru
Write-Output ('Live runner started. PID ' + $hinaProcess.Id)
Write-Output 'Local site: http://127.0.0.1:5173'
Write-Output 'Status: .runtime/live/runner-state.json'
