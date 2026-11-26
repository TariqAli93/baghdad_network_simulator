"""Process bootstrap for CPU-only Sionna RT.

Call :func:`init` once, before anything imports ``mitsuba`` or ``sionna.rt``.
It applies (in this order) an optional hard memory cap, an optional CPU
affinity, the LLVM library path Dr.Jit needs on Windows, and the CPU variant.

The memory cap and the affinity must be in place before Dr.Jit starts its
thread pool and allocator, which is why they live here and not in the callers.
"""

from __future__ import annotations

import ctypes
import os
import struct
import sys
from pathlib import Path

CPU_VARIANT = "llvm_ad_mono_polarized"
LLVM_ENV = "DRJIT_LIBLLVM_PATH"
CACHE_ENV = "DRJIT_CACHE_DIR"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Compiled ray-tracing kernels are kept here so that only the very first run of
# a given configuration has to compile anything (see run_isolated below).
KERNEL_CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "drjit"
_LLVM_CANDIDATES = (
    Path(r"C:\Program Files\LLVM\bin\LLVM-C.dll"),
    Path(r"C:\Program Files (x86)\LLVM\bin\LLVM-C.dll"),
)

# The job handle must stay open for the cap to remain in force.
_job_handle = None


def find_llvm() -> Path:
    """Return the LLVM shared library Dr.Jit should load, or raise with a fix."""
    override = os.environ.get(LLVM_ENV)
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise FileNotFoundError(f"{LLVM_ENV} points to a missing file: {override}")
    if sys.platform != "win32":
        raise FileNotFoundError(f"Set {LLVM_ENV} to the LLVM shared library.")
    for path in _LLVM_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "LLVM-C.dll not found. Install LLVM 18.1.8 "
        "(winget install --id LLVM.LLVM -e --version 18.1.8) "
        f"or set {LLVM_ENV} to the full path of LLVM-C.dll."
    )


# --- Windows Job Object memory cap -------------------------------------------------

_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_EXTENDED_LIMIT_INFORMATION = 9


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("Basic", _BasicLimit),
        ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kernel32():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = ctypes.c_void_p
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.QueryInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    return k32


def cap_memory(limit_gb: float) -> None:
    """Put this process in a job whose committed memory may not exceed the limit.

    The limit applies to committed (pagefile-backed) memory, which is stricter
    than physical RAM. Allocations beyond it fail, so an over-budget run ends
    with an out-of-memory error instead of freezing the machine.
    """
    global _job_handle
    if sys.platform != "win32":
        raise OSError("The memory cap is implemented for Windows only.")
    if _job_handle is not None:
        raise RuntimeError("Memory cap already applied.")
    k32 = _kernel32()
    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _ExtendedLimit()
    info.Basic.LimitFlags = _JOB_OBJECT_LIMIT_JOB_MEMORY | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    info.JobMemoryLimit = int(limit_gb * 1024**3)
    if not k32.SetInformationJobObject(
            job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    _job_handle = job


def peak_job_commit_bytes() -> int | None:
    """Peak committed memory of the capped job, or None when no cap is active."""
    if _job_handle is None:
        return None
    info = _ExtendedLimit()
    if not _kernel32().QueryInformationJobObject(
            _job_handle, _EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(info.PeakJobMemoryUsed)


# --- CPU topology ---------------------------------------------------------------


def cpu_topology() -> list[dict]:
    """Logical CPUs with their physical core and efficiency class (Windows).

    On hybrid Intel CPUs the performance cores report a higher efficiency
    class than the efficient cores. Returns an empty list where unsupported.
    """
    if sys.platform != "win32":
        return []
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    needed = ctypes.c_ulong(0)
    k32.GetSystemCpuSetInformation(None, 0, ctypes.byref(needed), None, 0)
    buf = ctypes.create_string_buffer(needed.value)
    if not k32.GetSystemCpuSetInformation(buf, needed, ctypes.byref(needed), None, 0):
        return []
    cpus, offset = [], 0
    while offset < needed.value:
        size, _type, _id, _group, logical, core, _llc, _numa, eff = struct.unpack_from(
            "<IIIHBBBBB", buf.raw, offset)
        cpus.append({"cpu": logical, "core": core, "efficiency_class": eff})
        offset += size
    return sorted(cpus, key=lambda c: c["cpu"])


def performance_cpus(one_thread_per_core: bool = False) -> list[int]:
    """Logical CPU indices of the performance cores (all CPUs if not hybrid)."""
    topo = cpu_topology()
    if not topo:
        return list(range(os.cpu_count() or 1))
    top = max(c["efficiency_class"] for c in topo)
    fast = [c for c in topo if c["efficiency_class"] == top]
    if one_thread_per_core:
        seen, picked = set(), []
        for c in fast:
            if c["core"] not in seen:
                seen.add(c["core"])
                picked.append(c["cpu"])
        return picked
    return [c["cpu"] for c in fast]


# --- Windows power throttling (EcoQoS) --------------------------------------------

_PROCESS_POWER_THROTTLING = 4                    # PROCESS_INFORMATION_CLASS.ProcessPowerThrottling
_THROTTLE_EXECUTION_SPEED = 0x1                  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED


def disable_power_throttling() -> bool:
    """Ask Windows never to run this process with EcoQoS (efficiency cores, low clocks).

    Windows 11 may treat a worker started from a background window as background work and
    confine it to the efficiency cores of a hybrid CPU; ray tracing then ran 4-5x slower on
    about 4 busy cores (docs/benchmarks.md, section 11). This changes scheduling only, never
    results. Set BNS_ALLOW_POWER_THROTTLING=1 to keep the system default (for comparison).
    """
    if sys.platform != "win32" or os.environ.get("BNS_ALLOW_POWER_THROTTLING") == "1":
        return False

    class _State(ctypes.Structure):
        _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    state = _State(1, _THROTTLE_EXECUTION_SPEED, 0)    # control execution speed: never throttle
    ok = k32.SetProcessInformation(ctypes.c_void_p(k32.GetCurrentProcess()), _PROCESS_POWER_THROTTLING,
                                   ctypes.byref(state), ctypes.sizeof(state))
    return bool(ok)


# --- Entry point ----------------------------------------------------------------


def init(threads: int | None = None, mem_cap_gb: float | None = None,
         cpus: list[int] | None = None, backend: str = "cpu") -> dict:
    """Prepare this process for ray tracing on `backend` ("cpu" or "gpu"); return what was applied.

    CPU is the default and the production path. "gpu" selects the CUDA variant of the
    installed Mitsuba wheel and needs only an NVIDIA driver; it fails loudly otherwise.

    Raises if mitsuba was already imported with another variant, because
    Sionna RT does not support switching variants after import.
    """
    throttling_disabled = disable_power_throttling()
    if mem_cap_gb is not None:
        cap_memory(mem_cap_gb)
    if cpus is not None:
        import psutil
        psutil.Process().cpu_affinity(cpus)

    from bns.propagation.engine_settings import VARIANTS

    if backend not in VARIANTS:
        raise ValueError(f"backend must be one of {sorted(VARIANTS)}, not {backend!r}.")
    variant = VARIANTS[backend]
    if backend == "cpu":
        # Keep any CUDA runtime out of the picture on the CPU path.
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    llvm = find_llvm() if backend == "cpu" else _find_llvm_optional()
    if llvm is not None:
        os.environ[LLVM_ENV] = str(llvm)
    if CACHE_ENV not in os.environ:
        KERNEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        os.environ[CACHE_ENV] = str(KERNEL_CACHE_DIR)

    import mitsuba as mi

    current = mi.variant()
    if current is not None and current != variant:
        raise RuntimeError(f"mitsuba already uses variant {current!r}; call init() first.")
    try:
        mi.set_variant(variant)
    except Exception as exc:                        # no driver, no CUDA-capable GPU
        raise RuntimeError(f"Backend {backend!r} ({variant}) is not available here: {exc}") from exc

    import drjit as dr

    if threads is not None:
        dr.set_thread_count(threads)
    if mi.variant() != variant:
        raise RuntimeError(f"Variant {variant} not active (got {mi.variant()!r}).")

    return {
        "backend": backend,
        "variant": mi.variant(),
        "power_throttling_disabled": throttling_disabled,
        "gpu": gpu_description() if backend == "gpu" else None,
        "llvm_library": None if llvm is None else str(llvm),
        "kernel_cache_dir": os.environ[CACHE_ENV],
        "threads": dr.thread_count(),
        "cpu_affinity": cpus,
        "mem_cap_gb": mem_cap_gb,
    }


def _find_llvm_optional():
    try:
        return find_llvm()
    except Exception:
        return None


def gpu_description() -> str | None:
    """Name, driver and memory of the first NVIDIA GPU (nvidia-smi), or None."""
    import subprocess
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines() if out.returncode == 0 else []
    return lines[0].strip() if lines else None


_PROBE = ("import mitsuba as mi\n"
          "mi.set_variant('cuda_ad_mono_polarized')\n"
          "import drjit as dr\n"
          "x = dr.cuda.Float([1.0, 2.0, 3.0])\n"
          "dr.eval(x)\n"
          "print('GPU-OK', x.numpy().sum())\n")


def probe_gpu(timeout_s: float = 180.0) -> tuple[bool, str]:
    """Can this machine run the CUDA variant? Checked in a separate process.

    Returns (available, diagnostic). Nothing is installed or changed.
    """
    import subprocess
    desc = gpu_description()
    if desc is None:
        return False, "No NVIDIA GPU or driver found (nvidia-smi unavailable); the CPU backend is used."
    try:
        out = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return False, f"GPU found ({desc}) but the CUDA probe timed out after {timeout_s:.0f} s."
    if out.returncode == 0 and "GPU-OK" in out.stdout:
        return True, f"GPU available: {desc}."
    tail = [ln for ln in (out.stderr or out.stdout).strip().splitlines() if ln.strip()][-1:] or ["no output"]
    return False, f"GPU found ({desc}) but the CUDA variant failed: {tail[0][:300]}"


class Cancelled(RuntimeError):
    """The caller asked to stop; the worker was terminated and its output discarded."""


def _publish(staging_dir: Path, final_dir: Path) -> None:
    """Swap the staging folder in as the result; an earlier result is replaced only now."""
    import shutil

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    old = final_dir.with_name(final_dir.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if final_dir.exists():
        final_dir.rename(old)
    staging_dir.rename(final_dir)
    if old.exists():
        shutil.rmtree(old)


def _run_once(argv, env, on_line, should_cancel) -> int:
    import subprocess
    import threading
    import time

    process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", bufsize=1)

    def pump():
        for line in process.stdout:
            line = line.rstrip("\n")
            if on_line is None:
                print(line, flush=True)
            else:
                on_line(line)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    while process.poll() is None:
        if should_cancel is not None and should_cancel():
            process.kill()
            process.wait()
            reader.join(timeout=5)
            raise Cancelled("Worker cancelled.")
        time.sleep(0.1)
    reader.join(timeout=5)
    return process.returncode


def run_isolated(argv: list[str], staging_dir: Path, final_dir: Path,
                 max_attempts: int = 8, env: dict | None = None,
                 on_line=None, should_cancel=None) -> list[dict]:
    """Run a worker in a fresh process and keep its output only if it exits cleanly.

    Why: with Dr.Jit 1.5.0 and LLVM 16+ on Windows, compiling a kernel for the
    first time intermittently aborts ("JIT session error: Failed to materialize
    symbols") or corrupts the heap, which Windows reports when the process ends.
    Kernels that did compile are saved in the kernel cache, so a retry gets
    further, and a run that compiles nothing is stable. The rule is therefore:
    results count only from a process that exits with code 0; anything else is
    discarded and repeated. The worker must write everything into `staging_dir`.

    The worker's standard output is passed line by line to `on_line` (progress
    reports), or printed. `should_cancel` is polled; when it returns True the
    worker is killed, its output discarded and Cancelled raised. An existing
    `final_dir` is replaced only by the output of a clean run.

    Returns one record per attempt. Raises if no attempt exits cleanly.
    """
    import shutil
    import time

    staging_dir, final_dir = Path(staging_dir), Path(final_dir)
    attempts = []
    for attempt in range(1, max_attempts + 1):
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)
        start = time.perf_counter()
        try:
            code = _run_once(argv, env, on_line, should_cancel)
        except Cancelled:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        attempts.append({"attempt": attempt, "exit_code": code,
                         "seconds": round(time.perf_counter() - start, 2)})
        if code == 0:
            _publish(staging_dir, final_dir)
            return attempts
        if code == 1:
            # An ordinary Python exception: repeating it would fail the same way.
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise RuntimeError(f"Worker failed with a Python error (see traceback above): {argv}")
    shutil.rmtree(staging_dir, ignore_errors=True)
    raise RuntimeError(f"Worker never exited cleanly in {max_attempts} attempts: {attempts}")


def versions() -> dict:
    """Versions of the packages that determine the numerical results."""
    from importlib.metadata import version
    import platform

    names = ("sionna-rt", "mitsuba", "drjit", "numpy", "shapely", "pyproj")
    out = {name: version(name) for name in names}
    out["python"] = platform.python_version()
    out["platform"] = platform.platform()
    out["processor"] = platform.processor()
    return out
