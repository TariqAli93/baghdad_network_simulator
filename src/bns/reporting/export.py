"""Plain-text exports of a run: one CSV row per receiver cell, sites as GeoJSON.

Coordinates are written both in local metres (scene frame) and in WGS84 degrees,
so the results can be opened in a GIS without the project code.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


def cells_csv(path: Path, grid, transformer, outdoor, columns: dict[str, np.ndarray], label: str) -> None:
    """columns: name -> [y, x] array. Non-finite values are written as empty fields."""
    xs, ys = np.meshgrid(grid.x_centers, grid.y_centers)
    lon, lat = transformer.transform(xs, ys, direction="INVERSE")
    names = list(columns)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        f.write(f"# {label}\n")
        w = csv.writer(f)
        w.writerow(["x_m", "y_m", "lon", "lat", "outdoor", *names])
        for iy in range(xs.shape[0]):
            for ix in range(xs.shape[1]):
                row = [f"{xs[iy, ix]:.2f}", f"{ys[iy, ix]:.2f}", f"{lon[iy, ix]:.7f}", f"{lat[iy, ix]:.7f}",
                       int(outdoor[iy, ix])]
                for n in names:
                    v = columns[n][iy, ix]
                    if isinstance(v, (np.bool_, bool)):
                        row.append(int(v))
                    elif np.issubdtype(np.asarray(v).dtype, np.integer):
                        row.append(int(v))
                    else:
                        row.append(f"{float(v):.4f}" if np.isfinite(v) else "")
                w.writerow(row)


def sites_geojson(path: Path, transformer, placed: list, label: str) -> None:
    features = []
    for s in placed:
        lon, lat = transformer.transform(s.x, s.y, direction="INVERSE")
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                         "properties": {"site_id": s.candidate_id, "building_id": s.building_id,
                                        "x_m": s.x, "y_m": s.y, "antenna_height_m": s.z,
                                        "roof_height_m": s.roof_height_m,
                                        "roof_height_category": s.height_category}})
    Path(path).write_text(json.dumps({"type": "FeatureCollection", "label": label, "features": features},
                                     indent=1), encoding="utf-8")
