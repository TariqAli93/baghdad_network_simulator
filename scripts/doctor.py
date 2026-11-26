"""Environment diagnostics: can this machine install, run and trace? (no changes made)

    uv run python scripts/doctor.py [--quick] [--save]

Checks Python and package versions, LLVM, memory, CPU, disk, the CPU ray-tracing variant (in
a separate process), the optional GPU, the development dataset and its raw-data checksums,
the kernel and path-gain caches, the radio-configuration approval state and the app port.
Each line is PASS, WARN or FAIL. --quick skips the engine smoke test. --save writes the
result to outputs/acceptance/doctor-<UTC time>.json (local only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = {"sionna-rt": "2.2.0", "mitsuba": "3.9.1", "drjit": "1.5.0"}
SMOKE = ("import json, time\nfrom bns import runtime\ninfo = runtime.init()\nimport drjit as dr\n"
         "t = time.perf_counter()\nx = dr.llvm.Float(list(range(1000)))\ny = dr.sum(x * 2)\ndr.eval(y)\n"
         "print(json.dumps({'variant': info['variant'], 'threads': info['threads'], "
         "'seconds': round(time.perf_counter() - t, 2)}))\n")
results: list[dict] = []


def check(name: str, status: str, detail: str) -> None:
    results.append({"check": name, "status": status, "detail": detail})
    print(f"{status:4}  {name}: {detail}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    import psutil

    from bns import runtime

    v = sys.version_info
    check("Python", "PASS" if (v.major, v.minor) == (3, 13) else "FAIL", platform.python_version())
    for pkg, pin in PINS.items():
        try:
            got = version(pkg)
            check(f"package {pkg}", "PASS" if got == pin else "FAIL", f"{got} (required {pin})")
        except PackageNotFoundError:
            check(f"package {pkg}", "FAIL", "not installed: run setup.ps1 (uv sync --frozen)")
    try:
        check("LLVM", "PASS", str(runtime.find_llvm()))
    except FileNotFoundError as exc:
        check("LLVM", "FAIL", str(exc))
    mem = psutil.virtual_memory()
    total = mem.total / 2**30
    check("memory", "PASS" if total >= 15.0 else "WARN",
          f"{total:.1f} GB total, {mem.available / 2**30:.1f} GB available (target laptop: 16 GB)")
    cpus = runtime.cpu_topology()
    perf = runtime.performance_cpus(one_thread_per_core=True)
    check("CPU", "PASS", f"{platform.processor()}; {os.cpu_count()} logical CPUs; {len(perf)} performance cores"
          + (f" (hybrid: {len(cpus)} CPU sets)" if cpus else ""))
    free = shutil.disk_usage(ROOT).free / 2**30
    check("disk", "PASS" if free >= 5 else "WARN", f"{free:.0f} GB free on the project drive (5 GB recommended)")
    power = psutil.sensors_battery()
    if power is not None:
        check("power", "PASS" if power.power_plugged else "WARN",
              "on AC power" if power.power_plugged else "on battery: benchmarks will be slower and unrepresentative")
    if not args.quick:
        proc = subprocess.run([sys.executable, "-c", SMOKE], capture_output=True, text=True, cwd=ROOT, timeout=600)
        line = proc.stdout.strip().splitlines()[-1:] if proc.returncode == 0 else []
        check("CPU ray-tracing variant", "PASS" if line else "FAIL",
              line[0] if line else (proc.stderr.strip().splitlines() or ["no output"])[-1][:300])
    ok, message = runtime.probe_gpu() if not args.quick else (False, "skipped (--quick)")
    check("GPU (optional)", "PASS" if ok else "INFO", message)
    for name in ("tahrir_bab_al_sharqi", "tahrir_bab_al_sharqi_v2"):
        data, meta = ROOT / "data" / "raw" / "osm" / f"{name}.json", ROOT / "data" / "raw" / "osm" / f"{name}.meta.json"
        if not data.exists():
            check(f"OSM snapshot {name}", "FAIL", "missing")
            continue
        same = hashlib.sha256(data.read_bytes()).hexdigest() == json.loads(meta.read_text(encoding="utf-8"))["sha256"]
        check(f"OSM snapshot {name}", "PASS" if same else "FAIL",
              "SHA-256 matches" if same else "SHA-256 mismatch: git may have converted line endings; "
                                             "check out data/raw again (see README)")
    scene = ROOT / "data" / "scenes" / "tahrir_bab_al_sharqi_v2" / "osm" / "scene.xml"
    check("development dataset", "PASS" if scene.exists() else "WARN",
          "built" if scene.exists() else "not built: setup.ps1 builds it (scripts/build_dataset.py)")
    kernels = runtime.KERNEL_CACHE_DIR
    n_kernels = len(list(kernels.glob("*"))) if kernels.exists() else 0
    check("kernel cache", "PASS", f"{kernels} ({n_kernels} files; empty means first traces compile, slower)")
    n_maps = len(list((ROOT / "data" / "cache" / "pathgain").glob("*/*.json")))
    check("path-gain cache", "PASS", f"{n_maps} cached maps")
    try:
        from bns.analysis.radio_system import RadioSystem
        system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
        approved = system.approved_parameters()
        check("radio configuration", "PASS", f"loads; {len(approved)} research-baseline parameter(s); other "
              "values run as custom experiments")
    except Exception as exc:                        # noqa: BLE001 - report, do not crash
        check("radio configuration", "FAIL", str(exc))
    with socket.socket() as s:
        free_port = s.connect_ex(("127.0.0.1", 8501)) != 0
    check("app port 8501", "PASS" if free_port else "WARN", "free" if free_port else "in use (app already running?)")

    failed = [r for r in results if r["status"] == "FAIL"]
    print(f"\n{len(failed)} failure(s), {sum(r['status'] == 'WARN' for r in results)} warning(s).")
    if args.save:
        out = ROOT / "outputs" / "acceptance"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"doctor-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        path.write_text(json.dumps({"machine": {"processor": platform.processor(), "platform": platform.platform(),
                                                "memory_gb": round(total, 1), "logical_cpus": os.cpu_count()},
                                    "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "results": results}, indent=2), encoding="utf-8")
        print(f"Saved {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
