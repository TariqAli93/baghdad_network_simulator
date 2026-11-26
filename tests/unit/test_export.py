"""CSV and GeoJSON exports keep coordinates, labels and missing values honest."""

import csv
import json

import numpy as np

from bns.geospatial.grid import Grid
from bns.geospatial.sites import Candidate
from bns.geospatial.study_area import local_transformer
from bns.reporting.export import cells_csv, sites_geojson

T = local_transformer(33.328, 44.4085)
GRID = Grid((0.0, 0.0), (20.0, 10.0), 10.0, 1.5)       # 2 x 1 cells


def test_cells_csv_round_trips_values_and_leaves_missing_values_empty(tmp_path):
    out = tmp_path / "cells.csv"
    sinr = np.array([[12.5, -np.inf]])
    cells_csv(out, GRID, T, np.array([[True, False]]),
              {"sinr_db": sinr, "covered": np.array([[True, False]]), "serving_site": np.array([[0, -1]])},
              "Preliminary Simulation · Research Baseline · Incomplete data · Validation Pending")
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# Preliminary Simulation · Research Baseline · Incomplete data · Validation Pending"
    rows = list(csv.DictReader(lines[1:]))
    assert rows[0]["sinr_db"] == "12.5000" and rows[1]["sinr_db"] == ""
    assert rows[0]["covered"] == "1" and rows[1]["serving_site"] == "-1" and rows[1]["outdoor"] == "0"
    assert float(rows[0]["x_m"]) == -5.0 and abs(float(rows[0]["lat"]) - 33.328) < 1e-3


def test_sites_geojson_puts_the_site_at_its_geographic_position(tmp_path):
    out = tmp_path / "sites.geojson"
    sites_geojson(out, T, [Candidate("site-001", 0.0, 0.0, 58.0, "way/1", 55.0, 900.0, "observed")], "LABEL")
    data = json.loads(out.read_text(encoding="utf-8"))
    lon, lat = data["features"][0]["geometry"]["coordinates"]
    assert abs(lon - 44.4085) < 1e-9 and abs(lat - 33.328) < 1e-9
    assert data["label"] == "LABEL" and data["features"][0]["properties"]["roof_height_category"] == "observed"
