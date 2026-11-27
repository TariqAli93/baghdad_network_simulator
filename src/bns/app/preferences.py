"""Interface preferences kept on this computer (currently the language), so they survive a restart.

A small JSON file under outputs/app_state/ (local application state, git-ignored, like the run state
in outputs/app_runs/). Nothing scientific is stored here. Reading never fails: a missing or damaged
file means no preferences; a failed write is ignored (the choice still holds for the session).
Tests point BNS_PREFERENCES_FILE elsewhere so they never touch the user's file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV = "BNS_PREFERENCES_FILE"


def location(root: Path) -> Path:
    override = os.environ.get(ENV)
    return Path(override) if override else Path(root) / "outputs" / "app_state" / "preferences.json"


def load(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(path: Path, **values) -> None:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({**load(path), **values}, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
