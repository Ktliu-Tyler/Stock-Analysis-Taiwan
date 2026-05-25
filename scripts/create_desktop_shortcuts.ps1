<#
Create desktop shortcuts for the canonical Taiwan stock scanner project.

Shortcuts created:
- Stock Scanner Start.lnk
- Stock Scanner Stop.lnk
#>
param(
    [string]$StartName = "Stock Scanner Start",
    [string]$StopName = "Stock Scanner Stop"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [string]$Path,
        [string]$Arguments,
        [string]$Description
    )

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = $Description
    $shortcut.IconLocation = "$powershell,0"
    $shortcut.Save()
}

$startScript = Join-Path $projectRoot "scripts\start_stock_scanner.ps1"
$stopScript = Join-Path $projectRoot "scripts\stop_stock_scanner.ps1"

New-Shortcut `
    -Path (Join-Path $desktop "$StartName.lnk") `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -NoExit -File `"$startScript`"" `
    -Description "Start D:\taiwan_stock_scanner Taiwan stock scanner"

New-Shortcut `
    -Path (Join-Path $desktop "$StopName.lnk") `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$stopScript`" -Pause" `
    -Description "Stop the local Taiwan stock scanner on port 8000"

Write-Host "Created desktop shortcuts:"
Write-Host "- $StartName.lnk"
Write-Host "- $StopName.lnk"
Write-Host "Project: $projectRoot"
