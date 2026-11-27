"""File checksums of a delivery package (SHA256SUMS.txt) and their verification.

`scripts/make_distribution.py` writes SHA256SUMS.txt into the package; `scripts/doctor.py`
verifies it on the student's computer. Quality reports under outputs/datasets/ are rebuilt by
setup.ps1 together with the scenes, so they are not listed. Lines use the sha256sum format
("<hex>  <path>"), so `certutil -hashfile` or any sha256sum tool can check single files too.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

NAME = "SHA256SUMS.txt"
REGENERATED = ("outputs/datasets/",)          # rewritten by setup.ps1 (scripts/build_dataset.py)


def listed(path: str) -> bool:
    """Whether a package path is covered by the checksum list."""
    return path != NAME and not path.startswith(REGENERATED)


def checksum_text(files: dict[str, bytes]) -> str:
    """'<sha256>  <path>' per listed file, sorted by path."""
    return "".join(f"{hashlib.sha256(data).hexdigest()}  {path}\n"
                   for path, data in sorted(files.items()) if listed(path))


def verify(root: Path) -> dict | None:
    """{'checked', 'missing', 'changed'} against SHA256SUMS.txt in `root`; None without that file."""
    sums = Path(root) / NAME
    if not sums.exists():
        return None
    missing, changed, checked = [], [], 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, path = line.split("  ", 1)
        checked += 1
        target = Path(root) / path
        if not target.exists():
            missing.append(path)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            changed.append(path)
    return {"checked": checked, "missing": missing, "changed": changed}
