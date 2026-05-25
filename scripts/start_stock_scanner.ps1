<#
Start the Taiwan stock scanner from the canonical project folder.

Keep this PowerShell window open while the server is running.
Stop it with Ctrl+C, by closing this window, or by running stop_stock_scanner.ps1.
#>
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Lan
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

if ($Lan) {
    $HostAddress = "0.0.0.0"
}

$python = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$localUrl = "http://127.0.0.1:$Port/"
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Write-Host "Stock scanner already appears to be running on port $Port."
    Write-Host "Opening $localUrl"
    Start-Process $localUrl
    return
}

Write-Host "Project: $projectRoot"
Write-Host "URL: $localUrl"
Write-Host "Stop: press Ctrl+C in this window, close this window, or run the desktop Stop shortcut."
Write-Host ""

$openCommand = "Start-Sleep -Seconds 2; Start-Process '$localUrl'"
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $openCommand
)

& $python run_app.py --host $HostAddress --port $Port
