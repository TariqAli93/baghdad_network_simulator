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


# --- Entry point ----------------------------------------------------------------


def init(threads: int | None = None, mem_cap_gb: float | None = None,
         cpus: list[int] | None = None) -> dict:
    """Prepare this process for CPU ray tracing and return what was applied.

    Raises if mitsuba was already imported with another variant, because
    Sionna RT does not support switching variants after import.
    """
    if mem_cap_gb is not None:
        cap_memory(mem_cap_gb)
    if cpus is not None:
        import psutil
        psutil.Process().cpu_affinity(cpus)

    # Keep any CUDA runtime out of the picture; this project is CPU-first.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    llvm = find_llvm()
    os.environ[LLVM_ENV] = str(llvm)
    if CACHE_ENV not in os.environ:
        KERNEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        os.environ[CACHE_ENV] = str(KERNEL_CACHE_DIR)

    import mitsuba as mi

    current = mi.variant()
    if current is not None and current != CPU_VARIANT:
        raise RuntimeError(f"mitsuba already uses variant {current!r}; call init() first.")
    mi.set_variant(CPU_VARIANT)

    import drjit as dr

    if threads is not None:
        dr.set_thread_count(threads)
    if mi.variant() != CPU_VARIANT:
        raise RuntimeError(f"CPU variant not active (got {mi.variant()!r}).")

    return {
        "variant": mi.variant(),
        "llvm_library": str(llvm),
        "kernel_cache_dir": os.environ[CACHE_ENV],
        "threads": dr.thread_count(),
        "cpu_affinity": cpus,
        "mem_cap_gb": mem_cap_gb,
    }


def run_isolated(argv: list[str], staging_dir: Path, final_dir: Path,
                 max_attempts: int = 8, env: dict | None = None) -> list[dict]:
    """Run a worker in a fresh process and keep its output only if it exits cleanly.

    Why: with Dr.Jit 1.5.0 and LLVM 16+ on Windows, compiling a kernel for the
    first time intermittently aborts ("JIT session error: Failed to materialize
    symbols") or corrupts the heap, which Windows reports when the process ends.
    Kernels that did compile are saved in the kernel cache, so a retry gets
    further, and a run that compiles nothing is stable. The rule is therefore:
    results count only from a process that exits with code 0; anything else is
    discarded and repeated. The worker must write everything into `staging_dir`.

    Returns one record per attempt. Raises if no attempt exits cleanly.
    """
    import shutil
    import subprocess
    import time

    attempts = []
    for attempt in range(1, max_attempts + 1):
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)
        start = time.perf_counter()
        code = subprocess.run(argv, env=env).returncode
        attempts.append({"attempt": attempt, "exit_code": code,
                         "seconds": round(time.perf_counter() - start, 2)})
        if code == 0:
            if final_dir.exists():
                shutil.rmtree(final_dir)
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            staging_dir.rename(final_dir)
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
