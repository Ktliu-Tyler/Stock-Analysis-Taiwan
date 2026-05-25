<#
Stop the local Taiwan stock scanner server.

By default this stops the Python process listening on port 8000.
#>
param(
    [int]$Port = 8000,
    [switch]$Pause
)

$ErrorActionPreference = "Continue"

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "No stock scanner server is listening on port $Port."
    if ($Pause) {
        Read-Host "Press Enter to close"
    }
    return
}

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    if ($process.ProcessName -notmatch "python|py") {
        Write-Warning "Port $Port is owned by $($process.ProcessName). Skipping PID $processId to avoid stopping the wrong app."
        continue
    }
    Write-Host "Stopping $($process.ProcessName) PID $processId..."
    Stop-Process -Id $processId -Force
}

Start-Sleep -Seconds 1
Write-Host "Stop command finished."
if ($Pause) {
    Read-Host "Press Enter to close"
}
