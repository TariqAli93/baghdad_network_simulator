"""The ray tracer against closed-form physics. Opt-in: `uv run pytest -m engine`.

Each test runs one validation experiment through the real engine (in an
isolated worker, like every simulation) and checks the physics it reports.
"""

import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.engine


OUT = Path(tempfile.mkdtemp(prefix="bns-engine-tests-"))     # never the committed Phase 0 records


def run_experiment(name: str) -> dict:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "poc_validate.py"), name], cwd=ROOT,
                   env={**os.environ, "BNS_PHASE0_OUT": str(OUT)})
    return json.loads((OUT / name / "result.json").read_text())


def test_free_space_matches_friis_at_every_band():
    result = run_experiment("e1")
    assert result["orientation_ok"], "grid axes are swapped"
    for band in result["bands"]:
        assert abs(band["mean_db"]) < 0.01
        assert band["max_abs_db"] <= result["tolerances"]["analytic_max_abs_db"]
    errors = [row["max_abs_db"] for row in result["convergence_3p5ghz"]]
    assert errors == sorted(errors, reverse=True), "error must fall as rays are added"


def test_ground_reflection_matches_fresnel_and_shows_brewster_dip():
    result = run_experiment("e2")
    assert result["checks"] == {"matches_slab_formula": True,
                                "brewster_dip_for_vertical": True,
                                "no_dip_for_horizontal": True}
    for row in result["rows"]:
        assert row["reflectance_max_abs_error"] < 0.005


def test_diffraction_follows_knife_edge_theory_near_the_shadow_boundary():
    result = run_experiment("e3")
    for row in result["rows"]:
        assert abs(row["near_boundary_difference_db"]) <= result["tolerances"]["diffraction_db"]
        assert abs(row["scaling_measured_db"] - row["scaling_expected_db"]) <= 2.0
        assert row["shadow_cells_without_energy"] == 0
    losses = [row["deep_shadow_measured_db"] for row in result["rows"]]
    assert losses == sorted(losses), "higher bands must lose more in the shadow"
