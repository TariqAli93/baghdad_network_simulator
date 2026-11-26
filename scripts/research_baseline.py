"""Compare the configuration files with the recorded research baseline (default), or record it.

    uv run python scripts/research_baseline.py
    uv run python scripts/research_baseline.py --record --note "why the baseline changed" --recorded-on 2026-11-27

Without --record: lists every baseline item as baseline / modified / not recorded. Modified
items do not block anything except research-baseline runs; other runs are custom experiments.
--record makes the current configuration the research baseline: use it only for a deliberate,
documented change of the baseline (e.g. a candidate-threshold refinement within the approved
method), and describe it in docs/approval-record.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from bns.analysis import research_baseline as rb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--note")
    parser.add_argument("--recorded-on")
    args = parser.parse_args()
    if args.record:
        if not (args.note and args.recorded_on):
            parser.error("--record needs --note (why) and --recorded-on (date)")
        print(f"Wrote {rb.record(ROOT, note=args.note, recorded_on=args.recorded_on)}")
    found = rb.check(ROOT)
    for i in found:
        print(f"  {i.state:13s} {i.name}")
    changed = [i for i in found if i.state != "baseline"]
    print(f"{len(found) - len(changed)} of {len(found)} items hold the research baseline"
          + (f"; {len(changed)} differ (runs with them are custom experiments)" if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
