"""Simulation workspace: editable stations -> the experiment's propagation jobs, staleness, evaluation.

The workspace must describe a station exactly as the experiment scripts do (identical cache keys),
so that a change needs ray tracing only when it changes a job key, and results computed from the
cache are the network model's results for exactly the stations shown.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml
from shapely.geometry import box

from bns.analysis import classification as cl
from bns.analysis.radio_system import RadioSystem
from bns.app import workspace as ws
from bns.geospatial.grid import outdoor_mask
from bns.geospatial.heights import Building, HeightRecord
from bns.geospatial.study_area import StudyArea
from bns.propagation import atmosphere as atm
from bns.simulation import experiment as ex
from bns.simulation.cache import PathGainCache
from bns.simulation.network import network
from bns.simulation.setup import SimulationConfig, sector_antennas

ROOT = Path(__file__).resolve().parents[2]


def building(bid, polygon, height, category="observed", tags=None):
    return Building(bid, polygon, dict(tags or {}),
                    HeightRecord(height, category, "manual:test", "measured", bid))


TALL = building("way/1", box(-60, -60, -20, -20), 30.0)                       # meets the site rule
LOW = building("way/2", box(20, 20, 30, 30), 6.0)                             # too low, too small
MONUMENT = building("way/3", box(40, -60, 60, -40), 25.0, tags={"historic": "monument"})


@pytest.fixture
def exp(tmp_path):
    scene = tmp_path / "scene"
    (scene / "meshes").mkdir(parents=True)
    (scene / "scene.xml").write_text("<scene version='2.1.0'/>", encoding="utf-8")
    area = StudyArea("toy", "development fixture", False, 33.34, 44.42, (200.0, 200.0), 50.0)
    system = RadioSystem.load(ROOT / "configs" / "radio_system.yaml")
    config = SimulationConfig.load(ROOT / "configs" / "simulation.yaml")
    profile = config.profile("standard")                    # the research-baseline profile
    grid = area.receiver_grid(profile.cell_size_m, system.require("rx_height_m", mode="development"))
    buildings = [TALL, LOW, MONUMENT]
    site_rule = yaml.safe_load((ROOT / "configs" / "site_rule.yaml").read_text(encoding="utf-8"))
    baseline, _ = atm.load_conditions(ROOT / "configs" / "atmosphere.yaml")
    e = ex.Experiment(ROOT, area, "osm", "development", profile, system, config, ex.load_scenarios(ROOT), baseline,
                      "test", scene, {}, buildings, grid, outdoor_mask(grid, [b.polygon for b in buildings]),
                      sector_antennas(system, mode="development", polarization=config.polarization),
                      system.require("antenna_height_above_roof_m", mode="development"), site_rule=site_rule,
                      classification=cl.Classification(cl.BASELINE, cl.INCOMPLETE, cl.PENDING))
    return e


@pytest.fixture
def ctx(exp):
    return ws.Context.from_experiment(exp)


def template(ctx, **changes):
    return replace(ws.StationTemplate.baseline(ctx), **changes)


def keys(jobs):
    return {sj.job.key() for js in jobs.values() for sj in js}


# ---------------------------------------------------------------- same description as the experiment scripts
def test_a_baseline_station_has_the_experiments_sector_antennas(ctx, exp):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    assert ws.antennas(s, exp.config.polarization) == exp.antennas


def test_a_station_on_a_rule_roof_traces_exactly_the_experiments_jobs(ctx, exp):
    [candidate] = ex.place_sites(exp, ["way/1"])
    s = ws.place(ctx, -40, -40, template(ctx), [])
    assert (s.x, s.y, s.antenna_height_m) == pytest.approx((candidate.x, candidate.y, candidate.z))
    expected = {j.key() for js in ex.jobs_for(exp, [candidate]).values() for _, j in js}
    assert keys(ws.jobs(ctx, [s])) == expected


def test_every_band_and_sector_of_every_enabled_station_is_one_job(ctx):
    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [a])
    jobs = ws.jobs(ctx, [a, b])
    assert set(jobs) == {sc["id"] for sc in ctx.exp.scenarios}
    assert all(len(js) == 2 * 3 for js in jobs.values())
    assert all(len(js) == 3 for js in ws.jobs(ctx, [a, replace(b, enabled=False)]).values())


# ---------------------------------------------------------------- what needs ray tracing
@pytest.mark.parametrize("change", [dict(tx_power_dbm=40.0), dict(enabled=True)])
def test_radio_only_station_changes_keep_every_job_key(ctx, change):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    assert keys(ws.jobs(ctx, [replace(s, **change)])) == keys(ws.jobs(ctx, [s]))


@pytest.mark.parametrize("change", [dict(antenna_height_m=40.0), dict(downtilt_deg=4.0), dict(azimuth_deg=30.0),
                                    dict(pattern="iso")])
def test_antenna_changes_alter_every_job_key_of_the_station(ctx, change):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    assert not keys(ws.jobs(ctx, [replace(s, **change)])) & keys(ws.jobs(ctx, [s]))


def test_fewer_sectors_reuse_the_trace_of_the_sector_that_keeps_its_bearing(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    three, two = ws.jobs(ctx, [s]), ws.jobs(ctx, [replace(s, sectors=2)])          # 0/120/240 -> 0/180
    assert keys(two) & keys(three) == {sj.job.key() for js in three.values() for sj in js if sj.sector == 0}


def test_moving_a_station_alters_its_job_keys_and_keeps_its_properties(ctx):
    s = replace(ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), []), tx_power_dbm=43.0)
    moved = ws.move(ctx, s, 10, 70, template(ctx, hypothetical_height_m=25.0), [])
    assert (moved.x, moved.y, moved.tx_power_dbm, moved.antenna_height_m) == (10, 70, 43.0, 25.0)
    assert not keys(ws.jobs(ctx, [moved])) & keys(ws.jobs(ctx, [s]))


def test_the_receiver_grid_and_ray_count_are_part_of_the_job_keys(ctx, exp):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    finer = ws.Context.from_experiment(replace(exp, grid=replace(exp.grid, height_m=2.0)))
    more = ws.Context.from_experiment(replace(exp, profile=replace(exp.profile, rays_per_site=int(2e9))))
    gpu = replace(ctx, engine={**ctx.engine, "variant": "cuda_ad_mono_polarized"})
    for other in (finer, more, gpu):
        assert not keys(ws.jobs(other, [s])) & keys(ws.jobs(ctx, [s]))


def test_trace_status_counts_cached_and_missing_jobs_per_band(ctx, tmp_path):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    jobs = ws.jobs(ctx, [s])
    cache = PathGainCache(tmp_path / "cache")
    first = jobs["lte_1800"][0].job
    staging = tmp_path / "staging"
    staging.mkdir()
    PathGainCache.write_entry(staging, first.key(), np.zeros(ctx.exp.grid.shape), {"seconds": 1.0})
    cache.publish(staging, [first.key()])
    status = ws.trace_status(jobs, cache)
    assert (status["lte_1800"].cached, status["lte_1800"].missing) == (1, 2)
    assert all(st.cached == 0 and st.missing == 3 for sid, st in status.items() if sid != "lte_1800")
    assert not status["lte_1800"].complete


# ---------------------------------------------------------------- placement
def test_a_click_on_a_roof_places_a_rooftop_station_at_the_site_rule_point(ctx, exp):
    s = ws.place(ctx, -25, -55, template(ctx), [])                # anywhere on the roof
    spot = TALL.polygon.representative_point()
    assert s.mount == ws.ROOFTOP and s.building_id == "way/1"
    assert (s.x, s.y) == pytest.approx((spot.x, spot.y))
    assert s.antenna_height_m == pytest.approx(30.0 + exp.mast_height_m)
    assert s.meets_site_rule is True


def test_a_roof_outside_the_candidate_rule_is_allowed_but_recorded(ctx):
    s = ws.place(ctx, 25, 25, template(ctx), [])
    assert s.mount == ws.ROOFTOP and s.meets_site_rule is False


def test_open_ground_gives_a_hypothetical_station_only_with_an_explicit_height(ctx):
    with pytest.raises(ws.PlacementError, match="height"):
        ws.place(ctx, 0, 60, template(ctx), [])
    s = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [])
    assert s.mount == ws.HYPOTHETICAL and s.building_id is None and s.antenna_height_m == 25.0
    with pytest.raises(ws.PlacementError, match="rooftop"):
        ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0, allow_hypothetical=False), [])


def test_monuments_never_host_a_station_and_the_scene_bounds_are_respected(ctx):
    with pytest.raises(ws.PlacementError, match="monument"):
        ws.place(ctx, 50, -50, template(ctx), [])
    with pytest.raises(ws.PlacementError, match="outside"):
        ws.place(ctx, 500, 0, template(ctx, hypothetical_height_m=25.0), [])


def test_placement_errors_carry_a_code_for_the_interface(ctx):
    with pytest.raises(ws.PlacementError) as err:
        ws.place(ctx, 50, -50, template(ctx), [])
    assert err.value.code == "monument" and err.value.values == {"building": "way/3"}


def test_rebinding_to_another_height_model_keeps_the_mast_on_the_new_roof(ctx, exp):
    s = replace(ws.place(ctx, -40, -40, template(ctx), []), tx_power_dbm=43.0)
    h = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [s])
    taller = building("way/1", TALL.polygon, 36.0, "placeholder")
    other = ws.Context.from_experiment(replace(exp, buildings=[taller, LOW, MONUMENT]))
    kept, dropped = ws.rebind(other, [s, h], template(ctx))
    assert dropped == []
    assert kept[0].antenna_height_m == pytest.approx(36.0 + exp.mast_height_m) and kept[0].tx_power_dbm == 43.0
    assert kept[0].height_category == "placeholder" and kept[1] == h


def test_station_ids_are_unique_and_short(ctx):
    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 25, 25, template(ctx), [a])
    assert (a.station_id, b.station_id) == ("S1", "S2")


# ---------------------------------------------------------------- evaluation from the cache
def fake_cache(ctx, stations, seed=0):
    rng = np.random.default_rng(seed)
    return {sj.job.key(): (rng.uniform(1e-13, 1e-8, ctx.exp.grid.shape), {"seconds": 2.0})
            for js in ws.jobs(ctx, stations).values() for sj in js}


def test_evaluation_is_the_network_model_of_exactly_the_shown_stations(ctx, exp):
    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [a])
    maps = fake_cache(ctx, [a, b])
    sc = exp.scenarios[0]
    result = ws.evaluate(ctx, [a, b], sc, ws.RadioSettings.baseline(ctx), maps.get)
    jobs = ws.jobs(ctx, [a, b])[sc["id"]]
    stack = np.stack([maps[sj.job.key()][0] for sj in jobs])
    sector_site = np.array([sj.station for sj in jobs])
    loss = np.stack([ex.gas_loss_db(exp, sc, (s.x, s.y, s.antenna_height_m)) for s in (a, a, a, b, b, b)])
    expected = network(stack, sector_site, exp.outdoor, ex.radio_inputs(exp, sc), loss)
    np.testing.assert_array_equal(result.layers["sinr_db"], expected.radio.sinr_db)
    np.testing.assert_array_equal(result.layers["serving_station"], expected.serving_site)
    assert result.summary["coverage_fraction"] == expected.summary["coverage_fraction"]
    assert result.station_ids == ["S1", "S2"] and result.trace_seconds == pytest.approx(12.0)


def test_a_stations_power_shifts_only_the_power_received_from_it(ctx, exp):
    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [a])
    maps = fake_cache(ctx, [a, b])
    sc = exp.scenarios[0]
    radio = replace(ws.RadioSettings.baseline(ctx), interference_activity=0.0)    # no interference: SNR
    one = ws.evaluate(ctx, [a, b], sc, radio, maps.get)
    two = ws.evaluate(ctx, [a, replace(b, tx_power_dbm=b.tx_power_dbm - 3.0)], sc, radio, maps.get)
    still_a = (one.layers["serving_station"] == 0) & (two.layers["serving_station"] == 0)
    np.testing.assert_allclose(two.layers["rx_power_dbm"][still_a], one.layers["rx_power_dbm"][still_a])
    still_b = (one.layers["serving_station"] == 1) & (two.layers["serving_station"] == 1)
    assert still_b.any()
    np.testing.assert_allclose(two.layers["rx_power_dbm"][still_b], one.layers["rx_power_dbm"][still_b] - 3.0)


def test_a_traced_pattern_never_gets_an_added_antenna_gain(ctx, exp):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    sc = exp.scenarios[0]
    inputs = ws.radio_inputs(ctx, [s], sc, ws.RadioSettings.baseline(ctx))
    assert np.ravel(inputs.tx_power_dbm).tolist() == [exp.system.tx_power_for_path_gain_dbm(sc["id"], mode="development")] * 3


def test_evaluation_refuses_missing_traces_instead_of_guessing(ctx, exp):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    with pytest.raises(ws.MissingTraces):
        ws.evaluate(ctx, [s], exp.scenarios[0], ws.RadioSettings.baseline(ctx), {}.get)


def test_greedy_over_the_shown_stations_is_the_projects_interference_aware_greedy(ctx, exp):
    from bns.optimization.greedy import greedy_sinr_site_selection

    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [a])
    c = ws.place(ctx, 25, 25, template(ctx), [a, b])
    maps = fake_cache(ctx, [a, b, c], seed=3)
    sc, radio = exp.scenarios[0], ws.RadioSettings.baseline(ctx)
    result = ws.greedy(ctx, [a, b, c], sc, radio, maps.get, target=0.9)

    def coverage(selection):
        shown = [replace(s, enabled=i in selection) for i, s in enumerate((a, b, c))]
        return ws.evaluate(ctx, shown, sc, radio, maps.get).summary["coverage_fraction"]

    expected = greedy_sinr_site_selection(coverage, 3, 0.9)
    assert result.selected == expected.selected and result.coverage_after == pytest.approx(expected.coverage_after)


# ---------------------------------------------------------------- classification
def test_rule_roofs_with_baseline_values_stay_the_research_baseline(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    c = ws.classify(ctx, [s], ws.RadioSettings.baseline(ctx))
    assert c.configuration == cl.BASELINE and c.deviations == ()


def test_load_alone_is_a_sensitivity_analysis(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    c = ws.classify(ctx, [s], replace(ws.RadioSettings.baseline(ctx), interference_activity=0.5))
    assert c.configuration == cl.SENSITIVITY


@pytest.mark.parametrize(("station", "phrase"), [
    (lambda ctx: ws.place(ctx, 25, 25, template(ctx), []), "outside the candidate rule"),
    (lambda ctx: ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), []), "hypothetical"),
    (lambda ctx: replace(ws.place(ctx, -40, -40, template(ctx), []), tx_power_dbm=43.0), "tx_power_dbm = 43"),
    (lambda ctx: replace(ws.place(ctx, -40, -40, template(ctx), []), azimuth_deg=30.0), "bearings")])
def test_departures_from_the_site_rule_make_a_custom_experiment(ctx, station, phrase):
    c = ws.classify(ctx, [station(ctx)], ws.RadioSettings.baseline(ctx))
    assert c.configuration == cl.CUSTOM and any(phrase in d for d in c.deviations), c.deviations


# ---------------------------------------------------------------- saved runs
def test_stations_rebuilt_from_a_run_manifest_reproduce_its_recorded_jobs(ctx, exp):
    placed = ex.place_sites(exp, ["way/1"])
    jobs = ex.jobs_for(exp, placed)
    manifest = {"run_id": "multi_site-test", "kind": "multi_site", "sites": [s.__dict__ for s in placed],
                "sectors_per_site": [a.__dict__ for a in exp.antennas],
                "sector_positions_m": {s.candidate_id: ex.sector_positions(exp, s) for s in placed},
                "radio_parameters": exp.system.status_report(["tx_power_dbm"]),
                "jobs": [{"scenario": sid, "site": placed[i].candidate_id, "key": j.key()}
                         for sid, js in jobs.items() for i, j in js]}
    stations, check = ws.stations_from_run(ctx, manifest)
    assert [s.origin for s in stations] == ["run:multi_site-test"]
    assert check == {"recorded": 15, "identical": 15, "exact": True}


def test_a_run_from_before_the_roof_edge_rule_is_rebuilt_with_its_antennas_at_the_site_point(ctx, exp):
    [site] = ex.place_sites(exp, ["way/1"])
    old = [replace(a, orientation_rad=(2 * np.pi * k / 3, a.orientation_rad[1], 0.0)) for k, a in enumerate(exp.antennas)]
    point = (site.x, site.y, site.z)
    from bns.simulation.setup import site_jobs
    recorded = [j for sc in exp.scenarios for j in site_jobs(exp.scene_dir, sc["frequency_hz"], point, old, exp.grid,
                                                            exp.config, exp.profile.rays_per_site)]
    manifest = {"run_id": "old", "kind": "multi_site", "sites": [site.__dict__],
                "sectors_per_site": [a.__dict__ for a in old],             # yaw 0/120/240 = compass 90/330/210
                "radio_parameters": exp.system.status_report(["tx_power_dbm"]),
                "jobs": [{"key": j.key()} for j in recorded]}
    stations, check = ws.stations_from_run(ctx, manifest)
    assert check["exact"] and stations[0].antenna_position == ws.SITE_POINT
    c = ws.classify(ctx, stations, ws.RadioSettings.baseline(ctx))
    assert c.configuration == cl.CUSTOM
    assert any("site point" in d for d in c.deviations) and any("bearings 90/210/330" in d for d in c.deviations)


def test_job_labels_name_band_station_and_sector(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    labels = ws.job_labels(ws.jobs(ctx, [s]), [s])
    assert {(v["scenario"], v["station"], v["sector"]) for v in labels.values()} == \
        {(sc["id"], "S1", k) for sc in ctx.exp.scenarios for k in (1, 2, 3)}
    assert sorted({v["bearing_deg"] for v in labels.values()}) == [0.0, 120.0, 240.0]
