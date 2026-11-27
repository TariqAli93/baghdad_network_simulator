"""Build the clean distribution archive: current commit only, restricted paths removed.

    uv run python scripts/make_distribution.py [--ref HEAD] [--name NAME]

Uses `git archive` (no history, no untracked or ignored files), drops every path matching
configs/distribution.yaml (`restricted`: licences; `not_delivered`: development files), checks
that none remains and that every `required` pattern is present, and writes
dist/<name>.zip (default baghdad-network-simulator-<git describe>) with
  DISTRIBUTION.txt   what was excluded and why
  SHA256SUMS.txt     checksum of every delivered file (scripts/doctor.py verifies it)
and dist/<name>.zip.sha256 beside it. Uncommitted changes are never included: the archive is
exactly the commit.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bns import integrity  # noqa: E402

PREFIX = "baghdad-network-simulator/"


def restricted(path: str, patterns: list[dict]) -> str | None:
    for p in patterns:
        if fnmatch.fnmatch(path, p["pattern"]):
            return p["reason"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--name", help="archive name without .zip (default: baghdad-network-simulator-<describe>)")
    args = parser.parse_args()
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        print("Note: uncommitted changes exist; they are NOT in the archive (it holds exactly the commit).")
    commit = subprocess.run(["git", "rev-parse", "--short", args.ref], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    describe = subprocess.run(["git", "describe", "--tags", "--always", args.ref], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or commit
    config = yaml.safe_load((ROOT / "configs" / "distribution.yaml").read_text(encoding="utf-8"))
    patterns = config["restricted"] + (config.get("not_delivered") or [])
    # invalidated runs are not demonstration results: leave them out of the archive
    bad = (yaml.safe_load((ROOT / "configs" / "invalidated_runs.yaml").read_text(encoding="utf-8")) or {}).get("runs") \
        if (ROOT / "configs" / "invalidated_runs.yaml").exists() else {}
    patterns = patterns + [{"pattern": f"outputs/runs/*/{rid}/*", "reason": "invalidated run (configs/invalidated_runs.yaml)"}
                           for rid in (bad or {})]
    raw = subprocess.run(["git", "archive", "--format=zip", args.ref], cwd=ROOT, capture_output=True, check=True).stdout
    source = zipfile.ZipFile(io.BytesIO(raw))
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    target = out_dir / f"{args.name or f'baghdad-network-simulator-{describe}'}.zip"
    excluded, kept = [], {}
    for info in source.infolist():
        if info.is_dir():
            continue
        reason = restricted(info.filename, patterns)
        if reason:
            excluded.append((info.filename, reason))
        else:
            kept[info.filename] = source.read(info.filename)
    missing = [p for p in config.get("required") or [] if not any(fnmatch.fnmatch(k, p) for k in kept)]
    if missing:
        print(f"Check failed: required files missing from the commit: {missing}")
        return 1
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in kept.items():
            z.writestr(PREFIX + name, data)
        note = [f"Baghdad Network Simulator {describe} (commit {commit})",
                f"Built {datetime.now(timezone.utc).isoformat(timespec='seconds')} from the commit only (no git history).",
                "Start with START-HERE.txt. Every result carries its scientific classification (configuration, "
                "dataset, validation); none is a validated research result yet, and none is a measurement.",
                "Data licences and attribution: docs/licensing.md.",
                f"File checksums: {integrity.NAME} (checked by 'Diagnose problems.cmd').", "",
                "Excluded (configs/distribution.yaml):"]
        note += [f"  {path}  -- {reason}" for path, reason in excluded] or ["  nothing"]
        z.writestr(PREFIX + "DISTRIBUTION.txt", "\n".join(note) + "\n")
        z.writestr(PREFIX + integrity.NAME, integrity.checksum_text(kept))
    with zipfile.ZipFile(target) as z:
        leaked = [n for n in z.namelist() if restricted(n[len(PREFIX):], patterns)]
        has_git = any("/.git/" in n for n in z.namelist())
        damaged = z.testzip()
    if leaked or has_git or damaged:
        print(f"Check failed: restricted {leaked}, git data {has_git}, damaged entry {damaged}")
        target.unlink()
        return 1
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    print(f"{target} ({target.stat().st_size / 1e6:.1f} MB): {len(kept)} files, {len(excluded)} excluded")
    print(f"SHA-256 {digest}")
    for path, reason in excluded:
        print(f"  excluded {path}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
