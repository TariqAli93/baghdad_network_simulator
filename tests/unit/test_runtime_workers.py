"""Isolated workers: only a clean exit publishes results; crashes retry; cancel discards."""

import sys
import textwrap

import pytest

from bns import runtime

WORKER = textwrap.dedent("""
    import json, sys, time
    from pathlib import Path
    out, counter, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    attempt = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(attempt))
    (out / f"partial-{attempt}.txt").write_text("started")
    print(json.dumps({"progress": 0.5, "attempt": attempt}), flush=True)
    if mode == "crash-once" and attempt == 1:
        import os; os._exit(3)                      # like a native crash: no clean-up
    if mode == "python-error":
        raise ValueError("bad configuration")
    if mode == "slow":
        time.sleep(30)
    (out / "result.txt").write_text(f"attempt {attempt}")
    print(json.dumps({"progress": 1.0, "attempt": attempt}), flush=True)
""")


def setup(tmp_path, mode):
    script = tmp_path / "worker.py"
    script.write_text(WORKER)
    staging, final, counter = tmp_path / "staging", tmp_path / "final", tmp_path / "counter"
    argv = [sys.executable, str(script), str(staging), str(counter), mode]
    return argv, staging, final


def test_a_crashed_attempt_publishes_nothing_and_the_retry_is_kept(tmp_path):
    argv, staging, final = setup(tmp_path, "crash-once")
    lines = []
    attempts = runtime.run_isolated(argv, staging, final, on_line=lines.append)
    assert [a["exit_code"] for a in attempts] == [3, 0]
    assert sorted(p.name for p in final.iterdir()) == ["partial-2.txt", "result.txt"]
    assert (final / "result.txt").read_text() == "attempt 2"
    assert not staging.exists()
    assert any('"progress": 1.0' in line for line in lines)


def test_a_python_error_is_not_retried_and_leaves_nothing(tmp_path):
    argv, staging, final = setup(tmp_path, "python-error")
    with pytest.raises(RuntimeError, match="Python error"):
        runtime.run_isolated(argv, staging, final)
    assert not final.exists() and not staging.exists()


def test_cancellation_stops_the_worker_and_discards_its_output(tmp_path):
    argv, staging, final = setup(tmp_path, "slow")
    seen = []
    with pytest.raises(runtime.Cancelled):
        runtime.run_isolated(argv, staging, final, on_line=seen.append,
                             should_cancel=lambda: bool(seen))
    assert not final.exists() and not staging.exists()


def test_an_existing_result_is_replaced_only_by_a_clean_run(tmp_path):
    argv, staging, final = setup(tmp_path, "python-error")
    final.mkdir()
    (final / "result.txt").write_text("earlier good result")
    with pytest.raises(RuntimeError):
        runtime.run_isolated(argv, staging, final)
    assert (final / "result.txt").read_text() == "earlier good result"
