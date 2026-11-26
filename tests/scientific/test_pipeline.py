"""The production pipeline against closed-form physics. Opt-in: `uv run pytest -m engine`.

Every test traces through the real worker, the cache and the radio calculations,
in a temporary cache so that nothing is reused from earlier runs.
"""

from dataclasses import replace

import numpy as np
import pytest

from bns.core.units import linear_to_db
from bns.geospatial.grid import Grid
from bns.propagation import atmosphere as atm
from bns.simulation import propagation as prop
from bns.simulation.cache import PathGainCache
from bns.simulation.jobs import Antenna, Mechanisms
from bns.simulation.radio import RadioInputs, single_site
from bns.simulation.setup import SimulationConfig, site_jobs
from bns.validation.analytic import cell_averaged_friis, tr38901_element_gain_dbi

pytestmark = pytest.mark.engine
LOS_ONLY = Mechanisms(0, True, False, False, False, False, False)
GRID = Grid((0.0, 0.0), (400.0, 400.0), 10.0, 1.5)
RAYS = 10**8     # the far corners of this grid need it for a 0.25 dB worst-cell error (E1)


@pytest.fixture
def run(tmp_path, repo_root):
    config = replace(SimulationConfig.load(repo_root / "configs" / "simulation.yaml"), mechanisms=LOS_ONLY)
    cache = PathGainCache(tmp_path / "cache")
    calls = []

    def trace(position, antennas, frequency=3.5e9):
        jobs = site_jobs(None, frequency, position, antennas, GRID, config, RAYS)
        maps = prop.compute(jobs, cache, work_dir=tmp_path / "work",
                            on_progress=lambda d, t, info: calls.append(info))
        return [maps[j.key()] for j in jobs], jobs

    return trace, calls


def far_cells(position, min_distance):
    xs, ys = np.meshgrid(GRID.x_centers, GRID.y_centers)
    return np.hypot(xs - position[0], ys - position[1]) >= min_distance, xs, ys


def test_received_power_through_the_whole_pipeline_matches_friis_plus_link_budget(run):
    trace, calls = run
    tx = (20.0, -30.0, 25.0)
    [gain], jobs = trace(tx, [Antenna("iso", "V", (0.0, 0.0, 0.0))])
    loss = atm.attenuation_map_db(tx, GRID, atm.gas_specific_attenuation_db_per_km(3.5e9))
    inputs = RadioInputs(tx_power_dbm=46.0, rx_gain_dbi=0.0, noise_figure_db=9.0,
                         noise_temperature_k=290.0, bandwidth_hz=100e6,
                         coverage_definition="snr_db", coverage_threshold=-10.0,
                         interference_activity=1.0)
    result = single_site(gain, np.ones(GRID.shape, bool), inputs, loss)
    expected = 46.0 + linear_to_db(cell_averaged_friis(tx, GRID.x_centers, GRID.y_centers, 1.5,
                                                       10.0, 3.5e9)) - loss
    error = result.rx_power_dbm - expected
    assert abs(error.mean()) < 0.01 and np.abs(error).max() < 0.25
    assert result.noise_dbm == pytest.approx(-173.98 + 80.0 + 9.0, abs=0.01)
    assert result.summary["coverage_fraction"] == 1.0
    traced = len(calls)
    trace(tx, [Antenna("iso", "V", (0.0, 0.0, 0.0))])
    assert len(calls) == traced                         # second call served from the cache


def test_traced_sector_pattern_matches_3gpp_tr38901_in_the_horizontal_plane(run):
    trace, _ = run
    # 1 m above the receivers: rays from a transmitter in the measurement plane never cross it
    tx = (0.0, 0.0, 2.5)
    (iso, sector), _ = trace(tx, [Antenna("iso", "V", (0.0, 0.0, 0.0)),
                                  Antenna("tr38901", "V", (0.0, 0.0, 0.0))])
    far, xs, ys = far_cells(tx, 60.0)
    measured = linear_to_db(sector / iso)[far]
    expected = np.array([tr38901_element_gain_dbi((x, y, 1.5 - 2.5))
                         for x, y in zip(xs[far], ys[far], strict=True)])
    assert np.median(np.abs(measured - expected)) < 0.2
    assert np.percentile(np.abs(measured - expected), 95) < 0.5
    assert measured.max() == pytest.approx(8.0, abs=0.3) and measured.min() == pytest.approx(-22.0, abs=0.5)


def test_positive_downtilt_points_the_sector_below_the_horizon(run):
    trace, _ = run
    tx = (0.0, 0.0, 31.5)                               # 30 m above the receivers
    tilt = np.radians(10.0)
    (iso, down, up), _ = trace(tx, [Antenna("iso", "V", (0.0, 0.0, 0.0)),
                                    Antenna("tr38901", "V", (0.0, tilt, 0.0)),
                                    Antenna("tr38901", "V", (0.0, -tilt, 0.0))])
    far, xs, ys = far_cells(tx, 40.0)
    front = far & (np.abs(ys) < 30.0) & (xs > 0)
    for gain, orientation in ((down, (0.0, tilt, 0.0)), (up, (0.0, -tilt, 0.0))):
        measured = linear_to_db(gain / iso)[front]
        expected = np.array([tr38901_element_gain_dbi((x, y, 1.5 - 31.5), orientation)
                             for x, y in zip(xs[front], ys[front], strict=True)])
        assert np.median(np.abs(measured - expected)) < 0.3
    near = front & (xs < 80.0)                          # steep angles: downtilt must help here
    assert (linear_to_db(down / up)[near] > 1.0).all()
