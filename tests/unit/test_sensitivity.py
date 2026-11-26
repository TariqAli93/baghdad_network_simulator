"""Summary of one height variant, on a hand-built map of 2 sites x 6 cells."""

import numpy as np
import pytest

from bns.analysis.sensitivity import summarise_variant

# cells:            0      1      2      3      4      5(indoor)
LOS = np.array([[[1e-8,  0.0,   0.0,   0.0,   0.0,   1e-8]],
                [[0.0,   1e-9,  0.0,   0.0,   0.0,   0.0]]])
REFLECTED = np.array([[[1e-8,  1e-10, 0.0,   0.0,   0.0,   1e-8]],     # line of sight + reflections
                      [[0.0,   1e-9,  1e-11, 0.0,   0.0,   0.0]]])
FULL = np.array([[[1e-8,  1e-10, 0.0,   1e-13, 0.0,   1e-8]],          # + diffraction
                 [[0.0,   1e-9,  1e-11, 0.0,   0.0,   0.0]]])
OUTDOOR = np.array([[True, True, True, True, True, False]])


def summary(**kwargs):
    args = dict(thresholds_db=[95.0, 115.0], coverage_target=0.6)
    args.update(kwargs)
    return summarise_variant(LOS, REFLECTED, FULL, OUTDOOR, **args)


def test_line_of_sight_availability_per_site_and_for_any_site():
    s = summary()
    assert s["outdoor_cells"] == 5
    assert s["los_fraction_per_site"] == pytest.approx([0.2, 0.2])
    assert s["los_fraction_any_site"] == pytest.approx(0.4)


def test_shadow_zone_is_what_no_site_reaches_by_any_mechanism():
    s = summary()
    assert s["shadow_fraction_all_sites"] == pytest.approx(0.2)          # cell 4
    assert s["shadow_fraction_per_site"] == pytest.approx([0.4, 0.6])


def test_diffraction_share_counts_cells_reached_only_by_diffraction():
    s = summary()
    assert s["diffraction_only_fraction"] == pytest.approx(0.2)          # cell 3
    assert s["reflection_only_fraction"] == pytest.approx(0.2)           # cell 2 (no line of sight)


def test_best_server_path_loss_percentiles_ignore_unreached_cells_but_report_them():
    s = summary()
    # best path loss per outdoor cell: 80, 90, 110, 130, unreached
    assert s["best_path_loss_db"]["median"] == pytest.approx(100.0)
    assert s["best_path_loss_db"]["reached_cells"] == 4


def test_coverage_and_greedy_site_count_per_threshold():
    s = summary()
    tight, loose = s["coverage"]
    assert tight["max_path_loss_db"] == 95.0
    assert tight["coverage_all_sites"] == pytest.approx(0.4)
    assert tight["target_reached"] is False and tight["greedy_sites"] == [0, 1]
    assert loose["coverage_all_sites"] == pytest.approx(0.6)
    assert loose["target_reached"] is True
    assert loose["greedy_sites"] == [0, 1]             # both cover two cells; the tie goes to site 0
    assert loose["greedy_coverage_after"] == pytest.approx([0.4, 0.6])


def test_indoor_cells_never_count():
    everything_indoor_strong = FULL.copy()
    everything_indoor_strong[0, 0, 5] = 1.0
    s = summarise_variant(LOS, REFLECTED, everything_indoor_strong, OUTDOOR,
                          thresholds_db=[95.0], coverage_target=0.5)
    assert s["coverage"][0]["coverage_all_sites"] == pytest.approx(0.4)


def test_shapes_must_agree():
    with pytest.raises(ValueError):
        summarise_variant(LOS, REFLECTED, FULL[:1], OUTDOOR, thresholds_db=[100.0], coverage_target=0.5)
