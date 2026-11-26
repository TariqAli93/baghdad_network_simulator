"""Check (default) or renew the approval lock of the approved scientific values.

    uv run python scripts/approval_lock.py
    uv run python scripts/approval_lock.py --record --confirmed-by "supervisor, ..." --confirmed-on 2026-11-27

Without --record: lists every approved value as locked / changed / not recorded and exits 1
if any is not locked (research runs refuse those). --record renews the lock for the CURRENT
values: run it only after the supervisor has (re)confirmed them, and update
docs/approval-record.md and configs/approvals.yaml with what was confirmed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bns.analysis import approval_lock as al  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--confirmed-by")
    parser.add_argument("--confirmed-on")
    args = parser.parse_args()
    if args.record:
        if not (args.confirmed_by and args.confirmed_on):
            parser.error("--record needs --confirmed-by and --confirmed-on (who confirmed, and when)")
        print(f"Wrote {al.record(ROOT, confirmed_by=args.confirmed_by, confirmed_on=args.confirmed_on)}")
    items = al.check(ROOT)
    for i in items:
        print(f"  {i.state:13s} {i.name}")
    bad = [i for i in items if i.state != "locked"]
    print(f"{len(items) - len(bad)} of {len(items)} approved values locked" + (f"; {len(bad)} need reconfirmation" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
