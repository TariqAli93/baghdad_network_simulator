<#
.SYNOPSIS
  First-time setup of the Baghdad Network Simulator (no administrator rights needed except for LLVM).

.DESCRIPTION
  1. Checks for uv and LLVM 18.1.8 and prints how to install them if missing (it installs nothing
     system-wide itself).
  2. Creates the Python environment exactly from uv.lock (uv sync --frozen). The first run needs
     internet access (Python 3.13 and about 1 GB of packages); later runs work offline.
  3. Builds the development dataset from the committed OpenStreetMap snapshot (offline).
  4. Runs the environment diagnostics (doctor.ps1).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>
param([switch]$SkipDataset)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "== Baghdad Network Simulator setup ==" -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed. Install it for your user (internet, no administrator rights):" -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "or: winget install --id astral-sh.uv -e   (then open a new PowerShell window)"
    exit 1
}
$llvm = if ($env:DRJIT_LIBLLVM_PATH) { $env:DRJIT_LIBLLVM_PATH } else { "C:\Program Files\LLVM\bin\LLVM-C.dll" }
if (-not (Test-Path $llvm)) {
    Write-Host "LLVM 18.1.8 is required by the CPU ray tracer and was not found ($llvm)." -ForegroundColor Yellow
    Write-Host "Install it (internet; Windows may ask for administrator approval):"
    Write-Host "  winget install --id LLVM.LLVM -e --version 18.1.8"
    Write-Host "or set DRJIT_LIBLLVM_PATH to an existing LLVM-C.dll, then run setup.ps1 again."
    exit 1
}
Write-Host "uv: $((uv --version) -join ' ')"
Write-Host "LLVM: $llvm"

Write-Host "`n== Python environment (uv sync --frozen) ==" -ForegroundColor Cyan
uv sync --frozen
if ($LASTEXITCODE -ne 0) { Write-Host "uv sync failed (internet needed the first time)." -ForegroundColor Red; exit 1 }

if (-not $SkipDataset) {
    $scene = Join-Path $PSScriptRoot "data\scenes\tahrir_bab_al_sharqi_v2\osm\scene.xml"
    if (-not (Test-Path $scene)) {
        Write-Host "`n== Development dataset ==" -ForegroundColor Cyan
        uv run python scripts/build_dataset.py --area tahrir_bab_al_sharqi_v2
        if ($LASTEXITCODE -ne 0) { Write-Host "Dataset build failed." -ForegroundColor Red; exit 1 }
    } else { Write-Host "`nDevelopment dataset already built." }
}

Write-Host "`n== Diagnostics ==" -ForegroundColor Cyan
uv run python scripts/doctor.py
if ($LASTEXITCODE -ne 0) { Write-Host "`nSetup finished with failures; see the FAIL lines above." -ForegroundColor Red; exit 1 }
Write-Host "`nSetup complete. Start the application with: .\run.ps1" -ForegroundColor Green
