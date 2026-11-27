<#
.SYNOPSIS
  Start the application and open it in the default browser.
  Students: double-click "2 - Start Baghdad Network Simulator.cmd" instead.

.DESCRIPTION
  Uses the project's own Python environment (.venv, created by setup.ps1), so it works offline
  and needs no other tool. Serves on localhost only (not reachable from other computers).
  Opens the browser as soon as the application answers. If the
  application is already running, it only opens the browser; if the port is taken by another
  program, the next free port is used. Closing this window stops the application.
.EXAMPLE
  .\run.ps1               # http://localhost:8501
  .\run.ps1 -Port 8502
  .\run.ps1 -NoBrowser
#>
param([int]$Port = 8501, [switch]$NoBrowser)
Set-Location -Path $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "The application is not installed yet. Double-click '1 - Install.cmd' first." -ForegroundColor Red
    exit 1
}

# health checks use 127.0.0.1: "localhost" tries IPv6 first and takes about 2 s to fall back to the
# IPv4-only server; the browser is still sent to http://localhost:<port>
function Test-App([int]$p) {
    try { (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$p/_stcore/health" -TimeoutSec 3).Content -eq "ok" }
    catch { $false }
}
function Test-PortInUse([int]$p) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", $p); $true } catch { $false } finally { $client.Close() }
}

if (Test-App $Port) {
    Write-Host "The application is already running at http://localhost:$Port - opening it in the browser."
    if (-not $NoBrowser) { Start-Process "http://localhost:$Port" }
    exit 0
}
$first = $Port
while (Test-PortInUse $Port) {
    $Port++
    if ($Port -gt $first + 10) { Write-Host "Ports $first to $Port are all in use; close other programs and try again." -ForegroundColor Red; exit 1 }
}
$url = "http://localhost:$Port"
Write-Host "Baghdad Network Simulator: starting at $url" -ForegroundColor Cyan
Write-Host "Keep this window open while you use the application. Close it to stop the application."
Write-Host "Every result states its scientific classification (configuration, dataset, validation)."
if (-not $NoBrowser) {
    # open the browser as soon as the application answers (at most about a minute)
    Start-Job -ScriptBlock {
        param($u, $p)
        for ($i = 0; $i -lt 120; $i++) {
            try { if ((Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$p/_stcore/health" -TimeoutSec 3).Content -eq "ok") { break } } catch {}
            Start-Sleep -Milliseconds 500
        }
        Start-Process $u
    } -ArgumentList $url, $Port | Out-Null
}
# localhost only: the application is not reachable from other computers on the network, and Streamlit
# then skips its online look-up of the computer's public address (offline operation)
& $python -m streamlit run app/main.py --server.port $Port --server.address localhost
