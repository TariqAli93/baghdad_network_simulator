"""Study areas: where the simulation happens, defined in configs/study_area.yaml.

An area is a rectangle of receivers around a centre point plus a margin of
surrounding buildings. Coordinates inside the project are metres in a local
transverse Mercator projection centred on the area (x east, y north).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pyproj import Transformer
from shapely.geometry import Polygon, box

from bns.geospatial.grid import Grid

ROLES = ("development fixture", "study district")


def local_transformer(lat0: float, lon0: float) -> Transformer:
    """WGS84 lon/lat -> transverse Mercator centred on (lat0, lon0), scale 1, metres."""
    crs = f"+proj=tmerc +lat_0={lat0} +lon_0={lon0} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m"
    return Transformer.from_crs("EPSG:4326", crs, always_xy=True)


@dataclass(frozen=True)
class StudyArea:
    name: str
    role: str                               # one of ROLES
    approved: bool                          # approved by the supervisor as the study district
    center_lat: float
    center_lon: float
    receiver_size_m: tuple[float, float]    # east-west, north-south extent of the receiver grid
    margin_m: float                         # buildings are kept this far beyond the receivers
    description: str = ""

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, not {self.role!r}.")
        if not (-90.0 <= self.center_lat <= 90.0 and -180.0 <= self.center_lon <= 180.0):
            raise ValueError("centre must be a valid latitude and longitude in degrees.")
        if min(self.receiver_size_m) <= 0 or self.margin_m < 0:
            raise ValueError("receiver size must be positive and the margin non-negative.")

    @property
    def is_research_dataset(self) -> bool:
        """Only an approved study district may carry thesis results."""
        return self.role == "study district" and self.approved

    @property
    def half_extent_m(self) -> tuple[float, float]:
        return (self.receiver_size_m[0] / 2.0 + self.margin_m,
                self.receiver_size_m[1] / 2.0 + self.margin_m)

    def transformer(self) -> Transformer:
        """WGS84 longitude/latitude -> local metres (use direction="INVERSE" to go back)."""
        return local_transformer(self.center_lat, self.center_lon)

    def bbox_degrees(self, pad_m: float = 20.0) -> tuple[float, float, float, float]:
        """South, west, north, east of the area including margin, padded by pad_m."""
        hx, hy = self.half_extent_m
        t = self.transformer()
        west, south = t.transform(-hx - pad_m, -hy - pad_m, direction="INVERSE")
        east, north = t.transform(hx + pad_m, hy + pad_m, direction="INVERSE")
        return south, west, north, east

    def clip_box(self) -> Polygon:
        hx, hy = self.half_extent_m
        return box(-hx, -hy, hx, hy)

    def receiver_box(self) -> Polygon:
        sx, sy = self.receiver_size_m
        return box(-sx / 2.0, -sy / 2.0, sx / 2.0, sy / 2.0)

    def receiver_grid(self, cell_size_m: float, height_m: float) -> Grid:
        return Grid((0.0, 0.0), tuple(self.receiver_size_m), cell_size_m, height_m)


def load_study_areas(path: Path) -> dict[str, StudyArea]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    areas = {}
    for name, entry in data["areas"].items():
        areas[name] = StudyArea(
            name=name, role=entry["role"], approved=bool(entry["approved"]),
            center_lat=float(entry["center"]["lat"]), center_lon=float(entry["center"]["lon"]),
            receiver_size_m=tuple(float(v) for v in entry["receiver_area_m"]),
            margin_m=float(entry["margin_m"]), description=entry.get("description", ""))
    return areas
