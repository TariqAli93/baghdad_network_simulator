<#
.SYNOPSIS
  Target-laptop acceptance measurements (docs/laptop-acceptance.md). Run on AC power.

.DESCRIPTION
  Writes everything to outputs\acceptance\<UTC time>\ (logs and summary.json):
    1. diagnostics (doctor)
    2. unit tests and engine tests, with their run time
    3. cold kernel compilation and warm repeat of one production-like trace (preview profile,
       empty temporary kernel cache), then the same trace at the standard profile
    4. one single-site run of all five bands at the preview profile: first uncached (traces,
       retries, peak memory), then again from the cache
  -Full adds the Phase 0 gate benchmark (scripts/poc_benchmark.py gate stability sustained;
  about an hour on the development PC). Cancellation is checked by hand in the app.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\benchmark.ps1
#>
param([switch]$Full)
Set-Location -Path $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $PSScriptRoot "outputs\acceptance\$stamp"
New-Item -ItemType Directory -Force $out | Out-Null
$summary = [ordered]@{ started_utc = $stamp; steps = [ordered]@{} }

function Invoke-Step([string]$Name, [string[]]$Command) {
    Write-Host "`n== $Name ==" -ForegroundColor Cyan
    $log = Join-Path $out "$Name.log"
    $t = Get-Date
    & uv @Command 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log | Where-Object { $_ -notmatch "JIT session error" }
    $code = $LASTEXITCODE
    $secs = [math]::Round(((Get-Date) - $t).TotalSeconds, 1)
    $retries = (Select-String -Path $log -Pattern "JIT session error" -SimpleMatch | Measure-Object).Count
    $summary.steps[$Name] = [ordered]@{ exit_code = $code; seconds = $secs; jit_error_lines = $retries; log = "$Name.log" }
    Write-Host "-> exit $code in $secs s ($retries JIT error lines)"
}

Invoke-Step "01-doctor" @("run", "python", "scripts/doctor.py", "--save")
Invoke-Step "02-unit-tests" @("run", "pytest", "-q")
Invoke-Step "03-engine-tests" @("run", "pytest", "-m", "engine", "-q")
Invoke-Step "04-trace-cold-preview" @("run", "python", "scripts/diagnose_trace_time.py", "--profile", "preview",
    "--antenna", "tr38901", "--cold", "--repeats", "2")
Invoke-Step "05-trace-standard" @("run", "python", "scripts/diagnose_trace_time.py", "--profile", "standard",
    "--antenna", "tr38901", "--repeats", "2")
Invoke-Step "06-single-site-uncached" @("run", "python", "scripts/run_multi_site.py", "--area", "tahrir_bab_al_sharqi_v2",
    "--mode", "development", "--profile", "preview", "--buildings", "way/939812415", "--backend", "cpu")
Invoke-Step "07-single-site-cached" @("run", "python", "scripts/run_multi_site.py", "--area", "tahrir_bab_al_sharqi_v2",
    "--mode", "development", "--profile", "preview", "--buildings", "way/939812415", "--backend", "cpu")
if ($Full) {
    Invoke-Step "08-phase0-gate" @("run", "python", "scripts/poc_benchmark.py", "gate", "stability", "sustained")
}
$summary["machine"] = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)
$summary["memory_gb"] = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$summary | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 (Join-Path $out "summary.json")
Write-Host "`nResults in $out. Copy them into docs/laptop-acceptance.md (section 'Recorded results')." -ForegroundColor Green
