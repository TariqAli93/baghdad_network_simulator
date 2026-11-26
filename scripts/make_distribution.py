"""Build the clean distribution archive: current commit only, restricted paths removed.

    uv run python scripts/make_distribution.py [--ref HEAD]

Uses `git archive` (no history, no untracked or ignored files), drops every path matching
configs/distribution.yaml, verifies that none remains, and writes
dist/baghdad-network-simulator-<ref>.zip with a DISTRIBUTION.txt listing what was excluded
and why. Uncommitted changes are never included: the archive is exactly the commit.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "baghdad-network-simulator/"


def restricted(path: str, patterns: list[dict]) -> str | None:
    for p in patterns:
        if fnmatch.fnmatch(path, p["pattern"]):
            return p["reason"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        print("Note: uncommitted changes exist; they are NOT in the archive (it holds exactly the commit).")
    commit = subprocess.run(["git", "rev-parse", "--short", args.ref], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    describe = subprocess.run(["git", "describe", "--tags", "--always", args.ref], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or commit
    patterns = yaml.safe_load((ROOT / "configs" / "distribution.yaml").read_text(encoding="utf-8"))["restricted"]
    raw = subprocess.run(["git", "archive", "--format=zip", args.ref], cwd=ROOT, capture_output=True, check=True).stdout
    source = zipfile.ZipFile(io.BytesIO(raw))
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    target = out_dir / f"baghdad-network-simulator-{describe}.zip"
    excluded, kept = [], 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for info in source.infolist():
            if info.is_dir():
                continue
            reason = restricted(info.filename, patterns)
            if reason:
                excluded.append((info.filename, reason))
                continue
            z.writestr(PREFIX + info.filename, source.read(info.filename))
            kept += 1
        note = [f"Baghdad Network Simulator {describe} (commit {commit})",
                f"Built {datetime.now(timezone.utc).isoformat(timespec='seconds')} from the commit only (no git history).",
                "All development results are labelled DEVELOPMENT - NOT APPROVED FOR RESEARCH.",
                "Data licences and attribution: docs/licensing.md.", "", "Excluded (configs/distribution.yaml):"]
        note += [f"  {path}  -- {reason}" for path, reason in excluded] or ["  nothing"]
        z.writestr(PREFIX + "DISTRIBUTION.txt", "\n".join(note) + "\n")
    with zipfile.ZipFile(target) as z:
        leaked = [n for n in z.namelist() if restricted(n[len(PREFIX):], patterns)]
        has_git = any("/.git/" in n for n in z.namelist())
    if leaked or has_git:
        print(f"Check failed: restricted {leaked}, git data {has_git}")
        target.unlink()
        return 1
    print(f"{target} ({target.stat().st_size / 1e6:.1f} MB): {kept} files, {len(excluded)} excluded")
    for path, reason in excluded:
        print(f"  excluded {path}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
