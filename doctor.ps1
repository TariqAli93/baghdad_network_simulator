<#
.SYNOPSIS
  Environment diagnostics (PASS / WARN / FAIL per check). Changes nothing.
.EXAMPLE
  .\doctor.ps1            # full check, including a CPU ray-tracing smoke test and the GPU probe
  .\doctor.ps1 -Quick     # skip the engine smoke test and GPU probe
  .\doctor.ps1 -Save      # also write outputs\acceptance\doctor-<time>.json
#>
param([switch]$Quick, [switch]$Save)
Set-Location -Path $PSScriptRoot
$argsList = @("run", "python", "scripts/doctor.py")
if ($Quick) { $argsList += "--quick" }
if ($Save) { $argsList += "--save" }
& uv @argsList
exit $LASTEXITCODE
