"""Path-gain cache: one entry per propagation job key, published only from clean workers.

An entry is two files: <key>.npz (the path-gain map) and <key>.json (its
manifest, including the SHA-256 of the .npz). The manifest is written last, and
an entry counts only if both exist and the checksum matches, so a half-written
or damaged entry is never read.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

_SCENE_FILES = ("scene.xml",)


def scene_fingerprint(scene_dir: Path | None) -> str:
    """Hash of what the ray tracer reads: scene.xml and every mesh file."""
    if scene_dir is None:
        return "empty-scene"
    scene_dir = Path(scene_dir)
    digest = hashlib.sha256()
    files = [scene_dir / name for name in _SCENE_FILES] + sorted((scene_dir / "meshes").glob("*.ply"))
    for path in files:
        digest.update(path.relative_to(scene_dir).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PathGainCache:
    def __init__(self, root: Path):
        self.root = Path(root)

    def paths(self, key: str) -> tuple[Path, Path]:
        folder = self.root / key[:2]
        return folder / f"{key}.npz", folder / f"{key}.json"

    def get(self, key: str):
        """(path gain, manifest) for a valid entry, else None."""
        data, meta = self.paths(key)
        if not (data.exists() and meta.exists()):
            return None
        manifest = json.loads(meta.read_text(encoding="utf-8"))
        if manifest.get("npz_sha256") != _sha256(data):
            return None
        with np.load(data) as archive:
            return archive["path_gain"], manifest

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    @staticmethod
    def write_entry(folder: Path, key: str, path_gain: np.ndarray, manifest: dict) -> None:
        """Write an entry into a worker's staging folder (not yet visible in the cache)."""
        folder = Path(folder)
        np.savez_compressed(folder / f"{key}.npz", path_gain=np.asarray(path_gain, dtype=np.float64))
        full = {**manifest, "key": key, "npz_sha256": _sha256(folder / f"{key}.npz")}
        (folder / f"{key}.json").write_text(json.dumps(full, indent=2), encoding="utf-8")

    def publish(self, staging: Path, keys: list[str]) -> None:
        """Move staged entries into the cache: data first, manifest last, each by atomic rename."""
        staging = Path(staging)
        for key in keys:
            for suffix in (".npz", ".json"):
                if not (staging / f"{key}{suffix}").exists():
                    raise FileNotFoundError(f"Entry {key} was not staged in {staging}.")
        for key in keys:
            data, meta = self.paths(key)
            data.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging / f"{key}.npz", data)
            os.replace(staging / f"{key}.json", meta)
