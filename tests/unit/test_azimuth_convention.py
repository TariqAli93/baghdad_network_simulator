"""Sector azimuth convention: compass bearings (user-facing) vs the ray tracer's scene frame.

Scene frame: x east, y north (local transverse Mercator centred on the area); the ray tracer's
yaw is measured counter-clockwise from +x. Compass bearing: clockwise from north. These tests
pin the conversion and check that every consumer of the yaw (pattern, roof-edge placement,
map arrows, cache keys) uses the same frame. They do NOT change the sector orientations.
"""

from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from bns.analysis.radio_system import RadioSystem
from bns.geospatial import sites
from bns.simulation import setup
from bns.simulation.jobs import Antenna
from bns.validation.analytic import tr38901_element_gain_dbi

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("bearing, east, north", [(0, 0, 1), (90, 1, 0), (180, 0, -1), (270, -1, 0)])
def test_compass_bearings_point_in_the_scene_frame_directions(bearing, east, north):
    az = setup.bearing_to_scene_azimuth_rad(bearing)
    assert (np.cos(az), np.sin(az)) == pytest.approx((east, north), abs=1e-12)


def test_conversion_round_trips():
    for bearing in np.arange(0.0, 360.0, 7.5):
        assert setup.scene_azimuth_to_bearing_deg(setup.bearing_to_scene_azimuth_rad(bearing)) == \
            pytest.approx(bearing % 360.0, abs=1e-9)


def test_the_implemented_sectors_face_compass_bearings_90_330_210():
    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    antennas = setup.sector_antennas(system, mode="development", polarization="V")
    yaws = [a.orientation_rad[0] for a in antennas]
    assert np.degrees(yaws) == pytest.approx([0.0, 120.0, 240.0])                 # unchanged scene yaws
    assert [setup.scene_azimuth_to_bearing_deg(y) for y in yaws] == pytest.approx([90.0, 330.0, 210.0])
    # the proposed compass bearings 0/120/240 would be scene yaws 90/330/210: a 30 deg rotation of the set
    proposed = sorted(np.degrees(setup.bearing_to_scene_azimuth_rad(b)) % 360 for b in (0, 120, 240))
    assert proposed == pytest.approx([90.0, 210.0, 330.0])


def test_roof_edge_placement_and_pattern_boresight_use_the_same_azimuth():
    roof = box(-20, -10, 20, 10)
    for yaw in np.radians([0.0, 120.0, 240.0, 90.0]):
        (x, y), = sites.edge_positions(roof, 0.0, 0.0, [yaw], inset_m=1.0)
        # the antenna stands on the side it faces, and its pattern peaks outward from the roof
        assert np.dot((x, y), (np.cos(yaw), np.sin(yaw))) > 0
        assert tr38901_element_gain_dbi((x, y, 0.0), (yaw, 0.0, 0.0)) == pytest.approx(8.0, abs=1e-9)
        assert tr38901_element_gain_dbi((-x, -y, 0.0), (yaw, 0.0, 0.0)) < -20.0


def test_a_different_sector_yaw_is_a_different_propagation_job():
    from bns.geospatial.grid import Grid
    from bns.simulation.jobs import PropagationJob
    from bns.simulation.jobs import Mechanisms

    grid = Grid((0.0, 0.0), (100.0, 100.0), 10.0, 1.5)
    mech = Mechanisms(max_depth=2, los=True, specular_reflection=True, diffraction=True, refraction=False,
                      diffuse_reflection=False, edge_diffraction=False)

    def job(yaw):
        return PropagationJob("scene", None, 3.5e9, (0.0, 0.0, 30.0), Antenna("tr38901", "V", (yaw, 0.17, 0.0)),
                              grid, mech, 10**8, (1,), {"variant": "llvm_ad_mono_polarized"})
    assert job(0.0).key() != job(np.pi / 2).key()
    assert job(0.0).key() == job(0.0).key()
