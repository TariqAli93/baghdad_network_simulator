<#
.SYNOPSIS
  First-time setup of the Baghdad Network Simulator.
  Students: double-click "1 - Install.cmd" instead.

.DESCRIPTION
  1. Checks for uv and LLVM 18.1.8. If one is missing and winget is available, asks whether to
     install it now (LLVM may show a Windows administrator prompt); otherwise prints the command.
  2. Creates the Python environment exactly from uv.lock (uv sync --frozen). The first run needs
     internet access (Python 3.13 and about 1 GB of packages); later runs work offline.
  3. Builds the datasets from the committed OpenStreetMap snapshot and 3D-GloBFP extract
     (offline): the development area, and the study district with its documented footprints and
     the Synthetic Urban Model (baseline, low, high). Datasets already built are kept.
  4. Runs the environment diagnostics (scripts/doctor.py).
  Running it again is safe: finished steps are skipped or repeated without changing results.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\setup.ps1
  powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Yes      # install missing tools without asking
#>
param([switch]$SkipDataset, [switch]$Yes)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Install-WithWinget([string]$What, [string[]]$WingetArgs) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
    $answer = if ($Yes) { "y" } else { Read-Host "$What is required. Install it now with winget? (Y/N)" }
    if ($answer -notmatch '^(y|yes)$') { return $false }
    & winget install @WingetArgs
    Update-SessionPath
    return $true
}

Write-Host "== Baghdad Network Simulator setup ==" -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Install-WithWinget "uv (the Python package manager)" @("--id", "astral-sh.uv", "-e") | Out-Null
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed. Install it for your user (internet, no administrator rights):" -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "or: winget install --id astral-sh.uv -e   (then run the installation again)"
    exit 1
}
$llvm = if ($env:DRJIT_LIBLLVM_PATH) { $env:DRJIT_LIBLLVM_PATH } else { "C:\Program Files\LLVM\bin\LLVM-C.dll" }
if (-not (Test-Path $llvm)) {
    Install-WithWinget "LLVM 18.1.8 (used by the CPU ray tracer)" @("--id", "LLVM.LLVM", "-e", "--version", "18.1.8") | Out-Null
}
if (-not (Test-Path $llvm)) {
    Write-Host "LLVM 18.1.8 is required by the CPU ray tracer and was not found ($llvm)." -ForegroundColor Yellow
    Write-Host "Install it (internet; Windows may ask for administrator approval):"
    Write-Host "  winget install --id LLVM.LLVM -e --version 18.1.8"
    Write-Host "or set DRJIT_LIBLLVM_PATH to an existing LLVM-C.dll, then run the installation again."
    exit 1
}
Write-Host "uv: $((uv --version) -join ' ')"
Write-Host "LLVM: $llvm"

Write-Host "`n== Python environment (uv sync --frozen) ==" -ForegroundColor Cyan
uv sync --frozen
if ($LASTEXITCODE -ne 0) { Write-Host "uv sync failed (internet is needed the first time)." -ForegroundColor Red; exit 1 }

if (-not $SkipDataset) {
    $study = "tahrir_bab_al_sharqi_study"
    $datasets = @(
        @{ Area = "tahrir_bab_al_sharqi_v2"; Variant = "osm"; Args = @() },
        @{ Area = $study; Variant = "osm+fp_3d_globfp"; Args = @("--add-footprints", "3d_globfp") },
        @{ Area = $study; Variant = "synthetic_urban-seed42+fp_3d_globfp"; Args = @("--height-model", "synthetic_urban", "--add-footprints", "3d_globfp") },
        @{ Area = $study; Variant = "synthetic_urban_low-seed42+fp_3d_globfp"; Args = @("--height-model", "synthetic_urban_low", "--add-footprints", "3d_globfp") },
        @{ Area = $study; Variant = "synthetic_urban_high-seed42+fp_3d_globfp"; Args = @("--height-model", "synthetic_urban_high", "--add-footprints", "3d_globfp") }
    )
    foreach ($d in $datasets) {
        $scene = Join-Path $PSScriptRoot "data\scenes\$($d.Area)\$($d.Variant)\scene.xml"
        if (Test-Path $scene) { Write-Host "`nDataset $($d.Area)/$($d.Variant) already built."; continue }
        Write-Host "`n== Dataset $($d.Area)/$($d.Variant) ==" -ForegroundColor Cyan
        uv run python scripts/build_dataset.py --area $d.Area @($d.Args)
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $scene)) { Write-Host "Dataset build failed." -ForegroundColor Red; exit 1 }
    }
}

Write-Host "`n== Diagnostics ==" -ForegroundColor Cyan
uv run python scripts/doctor.py
if ($LASTEXITCODE -ne 0) { Write-Host "`nSetup finished with failures; see the FAIL lines above." -ForegroundColor Red; exit 1 }
Write-Host "`nSetup complete. Start the application by double-clicking '2 - Start Baghdad Network Simulator.cmd'." -ForegroundColor Green
