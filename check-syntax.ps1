$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/start-hinaa.ps1", [ref]$null, [ref]$errors) | Out-Null
foreach ($e in $errors) {
    Write-Host "Line $($e.Extent.StartLineNumber): $($e.Message)"
}
