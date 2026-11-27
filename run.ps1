<#
.SYNOPSIS
  Start the application and open it in the default browser.
.EXAMPLE
  .\run.ps1               # http://localhost:8501
  .\run.ps1 -Port 8502
  .\run.ps1 -NoBrowser
#>
param([int]$Port = 8501, [switch]$NoBrowser)
Set-Location -Path $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Write-Host "uv not found: run setup.ps1 first." -ForegroundColor Red; exit 1 }
$url = "http://localhost:$Port"
Write-Host "Starting the Baghdad Network Simulator at $url (Ctrl+C stops it)."
Write-Host "Every result states its scientific classification (configuration, dataset, validation)."
if (-not $NoBrowser) {
    Start-Job -ScriptBlock { param($u) Start-Sleep -Seconds 6; Start-Process $u } -ArgumentList $url | Out-Null
}
uv run streamlit run app/main.py --server.port $Port
