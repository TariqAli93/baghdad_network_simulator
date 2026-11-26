"""Geometry helpers for the MATLAB cross-check package (scene as STL, receiver sampling).

MATLAB is an external verification tool; nothing here runs MATLAB.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def read_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Vertices [n, 3] and triangles [m, 3] of a binary little-endian PLY written by osm_scene.write_ply."""
    data = Path(path).read_bytes()
    end = data.index(b"end_header") + len(b"end_header\n")
    header = data[:end].decode("ascii").splitlines()
    nv = next(int(h.split()[2]) for h in header if h.startswith("element vertex"))
    nf = next(int(h.split()[2]) for h in header if h.startswith("element face"))
    if "format binary_little_endian 1.0" not in header:
        raise ValueError("Only binary little-endian PLY is supported.")
    vertices = np.frombuffer(data, dtype="<f4", count=nv * 3, offset=end).reshape(nv, 3).astype(float)
    record = np.dtype([("n", "u1"), ("i", "<i4", (3,))])
    faces = np.frombuffer(data, dtype=record, count=nf, offset=end + nv * 12)
    if np.any(faces["n"] != 3):
        raise ValueError("Only triangle faces are supported.")
    return vertices, faces["i"].astype(np.int64)


def write_stl(path: Path, vertices: np.ndarray, faces: np.ndarray, name: str = "scene") -> None:
    """Binary STL with outward normals as given by the face winding."""
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, length, out=np.zeros_like(normals), where=length > 0)
    with open(path, "wb") as f:
        f.write(name.encode("ascii")[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(faces)))
        rec = np.zeros(len(faces), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        rec["n"], rec["v"] = normals, tri
        f.write(rec.tobytes())


def merge(meshes: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    vs, fs, offset = [], [], 0
    for v, f in meshes:
        vs.append(v)
        fs.append(f + offset)
        offset += len(v)
    return np.vstack(vs), np.vstack(fs)


def sample_cells(mask: np.ndarray, classes: np.ndarray, per_class: int, seed: int = 0) -> list[tuple[int, int]]:
    """Up to `per_class` cells of each class value inside `mask`, reproducibly, sorted."""
    rng = np.random.default_rng(seed)
    picked = []
    for value in np.unique(classes[mask]):
        cells = np.argwhere(mask & (classes == value))
        take = min(per_class, len(cells))
        picked += [tuple(c) for c in cells[np.sort(rng.choice(len(cells), take, replace=False))]]
    return sorted(picked)
