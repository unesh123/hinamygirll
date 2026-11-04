param([switch]$Public, [switch]$Deploy, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$hinaRoot = Split-Path -Parent $PSScriptRoot
$hinaRuntime = Join-Path $hinaRoot '.runtime\live'
New-Item -ItemType Directory -Path $hinaRuntime -Force | Out-Null

# Local production preview is the default. Publishing requires explicit flags.
if ($Deploy -and -not $Public) {
    $Public = $true
}

$hinaPidFile = Join-Path $hinaRuntime 'runner.pid'
if (Test-Path -LiteralPath $hinaPidFile) {
    $hinaExistingPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $hinaPidFile -Raw).Trim(), [ref]$hinaExistingPid)) {
        $hinaExisting = Get-Process -Id $hinaExistingPid -ErrorAction SilentlyContinue
        if ($hinaExisting -and $hinaExisting.ProcessName -eq 'python') {
            Write-Output "Hina live runner is already active (PID $hinaExistingPid)."
            Write-Output "Local:  http://127.0.0.1:5173"
            Write-Output "See .runtime/live/runner-state.json for the active runner mode."
            return
        }
    }
    Remove-Item -LiteralPath $hinaPidFile -Force -ErrorAction SilentlyContinue
}

$hinaPython = Join-Path $hinaRoot 'apps\api\.venv\Scripts\python.exe'
$runnerScript = Join-Path $PSScriptRoot 'live_runner.py'
$argList = "`"$runnerScript`""
if ($Public) { $argList += " --public" }
if ($Deploy) { $argList += " --deploy" }
if ($Dev) { $argList += " --dev" }

$hinaStopFile = Join-Path $hinaRuntime 'stop-requested'
if (Test-Path -LiteralPath $hinaStopFile) { Remove-Item -LiteralPath $hinaStopFile -Force }

$hinaProcess = Start-Process -FilePath $hinaPython -ArgumentList $argList -WorkingDirectory $hinaRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hinaRuntime 'runner.out.log') -RedirectStandardError (Join-Path $hinaRuntime 'runner.err.log') -PassThru
Write-Output ('Live runner started. PID ' + $hinaProcess.Id)
Write-Output 'Local site:  http://127.0.0.1:5173'
if ($Public) { Write-Output 'Public tunnel requested; check runner-state.json for reachability.' }
if ($Deploy) { Write-Output 'Public deployment recovery requested.' }
Write-Output 'Status file: .runtime/live/runner-state.json'

