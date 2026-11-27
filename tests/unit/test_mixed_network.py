"""Mixed-generation networks: each station transmits on its own carriers, each with its own power and antenna;
carriers interfere only where their channels overlap (docs/assumptions.md section 11)."""

from dataclasses import asdict, replace

import numpy as np
import pytest
from test_workspace import ctx, exp, template  # noqa: F401  (fixtures)

from bns.analysis import classification as cl
from bns.app import workspace as ws
from bns.core.units import dbm_to_watt
from bns.simulation.network import network, spectral_overlap


def presets(ctx):
    return {c["id"]: c for c in ws.preset_carriers(ctx)}


def custom(ctx, preset_id, f_hz, b_hz):
    base = presets(ctx)[preset_id]
    return {**base, "id": f"{preset_id}.f{f_hz / 1e6:g}b{b_hz / 1e6:g}", "frequency_hz": f_hz, "bandwidth_hz": b_hz,
            "custom": True, "gas": "p676", "gas_db_per_km": 0.008, "preset_frequency_hz": base["frequency_hz"],
            "preset_bandwidth_hz": base["bandwidth_hz"]}


def network_of(ctx):
    """BS-01 4G, BS-02 5G, BS-03 candidate 6G, BS-04 all three (its 6G carrier tilted differently)."""
    a = ws.place(ctx, -40, -40, template(ctx), [])
    b = ws.place(ctx, 0, 60, template(ctx, hypothetical_height_m=25.0), [a])
    c = ws.place(ctx, 60, 0, template(ctx, hypothetical_height_m=30.0), [a, b])
    d = ws.place(ctx, -60, 60, template(ctx, hypothetical_height_m=20.0), [a, b, c])
    a = replace(a, carriers=(ws.StationCarrier.of(a, "lte_1800"),))
    b = replace(b, carriers=(ws.StationCarrier.of(b, "nr_3500", tx_power_dbm=40.0),))
    c = replace(c, carriers=(ws.StationCarrier.of(c, "c6g_8000", azimuth_deg=30.0),))
    d = replace(d, carriers=(ws.StationCarrier.of(d, "lte_1800"), ws.StationCarrier.of(d, "nr_3500"),
                             ws.StationCarrier.of(d, "c6g_8000", downtilt_deg=4.0)))
    return [a, b, c, d]


def cache_for(ctx, stations, carriers, seed=0):
    rng = np.random.default_rng(seed)
    return {sj.job.key(): (rng.uniform(1e-13, 1e-8, ctx.exp.grid.shape), {"seconds": 1.0})
            for js in ws.jobs(ctx, stations, carriers).values() for sj in js}


THREE = ("lte_1800", "nr_3500", "c6g_8000")


# ---------------------------------------------------------------- who transmits what
def test_each_station_traces_only_its_own_carriers(ctx):
    st = network_of(ctx)
    jobs = ws.jobs(ctx, st, [presets(ctx)[c] for c in THREE])
    ids = {cid: {st[sj.station].station_id for sj in js} for cid, js in jobs.items()}
    assert ids == {"lte_1800": {"S1", "S4"}, "nr_3500": {"S2", "S4"}, "c6g_8000": {"S3", "S4"}}
    assert all(len(js) == 6 for js in jobs.values())             # two stations x three sectors each


def test_each_carrier_of_a_station_has_its_own_antenna_settings(ctx):
    st = network_of(ctx)
    d, six = st[3], presets(ctx)["c6g_8000"]
    tilted = ws.jobs(ctx, [d], [six])["c6g_8000"]
    as_legacy = ws.jobs(ctx, [replace(d, carriers=None, downtilt_deg=4.0)], [six])["c6g_8000"]
    assert [sj.job.key() for sj in tilted] == [sj.job.key() for sj in as_legacy]
    lte = ws.jobs(ctx, [d], [presets(ctx)["lte_1800"]])["lte_1800"]
    assert [sj.job.antenna for sj in lte] != [sj.job.antenna for sj in tilted]


def test_disabling_one_carrier_leaves_the_others_unchanged(ctx):
    st = network_of(ctx)
    d = st[3]
    off = replace(d, carriers=tuple(replace(e, enabled=e.carrier_id != "c6g_8000") for e in d.carriers))
    carriers = [presets(ctx)[c] for c in THREE]
    before, after = ws.jobs(ctx, st, carriers), ws.jobs(ctx, [*st[:3], off], carriers)
    assert {st[sj.station].station_id for sj in after["c6g_8000"]} == {"S3"}
    for cid in ("lte_1800", "nr_3500"):
        assert [sj.job.key() for sj in after[cid]] == [sj.job.key() for sj in before[cid]]


def test_a_station_without_its_own_carriers_transmits_every_selected_carrier(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    assert s.carriers is None
    assert {cid for cid, js in ws.jobs(ctx, [s]).items() if js} == set(presets(ctx))


# ---------------------------------------------------------------- interference by spectral overlap
def test_carriers_that_do_not_overlap_do_not_interfere(ctx):
    st = network_of(ctx)
    carriers = [presets(ctx)[c] for c in THREE]
    maps = cache_for(ctx, st, carriers)
    radio = ws.RadioSettings.baseline(ctx)
    mixed = ws.evaluate(ctx, st, presets(ctx)["lte_1800"], radio, maps.get, carriers=carriers)
    only_4g = ws.evaluate(ctx, [st[0], st[3]], presets(ctx)["lte_1800"], radio, maps.get, carriers=carriers)
    np.testing.assert_array_equal(mixed.layers["sinr_db"], only_4g.layers["sinr_db"])
    np.testing.assert_array_equal(mixed.layers["interference_dbm"], only_4g.layers["interference_dbm"])
    assert mixed.summary["other_carriers"] == []


def test_the_same_carrier_on_two_stations_is_co_channel_as_before(ctx):
    st = network_of(ctx)
    nr = presets(ctx)["nr_3500"]
    maps = cache_for(ctx, st, [nr])
    radio = ws.RadioSettings.baseline(ctx)
    mixed = ws.evaluate(ctx, st, nr, radio, maps.get, carriers=[nr])
    b, d = st[1], st[3]
    legacy = [replace(b, carriers=None, tx_power_dbm=40.0), replace(d, carriers=None)]
    same = ws.evaluate(ctx, legacy, nr, radio, maps.get)
    np.testing.assert_array_equal(mixed.layers["sinr_db"], same.layers["sinr_db"])
    np.testing.assert_array_equal(mixed.layers["rx_power_dbm"], same.layers["rx_power_dbm"])


def test_an_overlapping_carrier_interferes_with_its_overlapping_share(ctx):
    st = network_of(ctx)
    nr, shifted = presets(ctx)["nr_3500"], custom(ctx, "nr_3500", 3.55e9, 100e6)
    b = replace(st[1], carriers=(ws.StationCarrier.of(st[1], shifted["id"], tx_power_dbm=40.0),))
    stations = [st[0], b, st[2], st[3]]
    carriers = [nr, shifted]
    maps = cache_for(ctx, stations, carriers)
    radio = ws.RadioSettings.baseline(ctx)
    e = ws.evaluate(ctx, stations, nr, radio, maps.get, carriers=carriers)
    assert spectral_overlap(3.5e9, 100e6, 3.55e9, 100e6) == pytest.approx(0.5)
    assert e.summary["other_carriers"] == [{"carrier": shifted["id"], "overlap": pytest.approx(0.5),
                                            "stations": ["S2"]}]
    alone = ws.evaluate(ctx, [st[3]], nr, radio, maps.get, carriers=[nr])
    external = 0.5 * ws.received_power_w(ctx, [b], shifted, radio, maps.get)
    expected = radio.interference_activity * (dbm_to_watt(alone.layers["interference_dbm"]) + external)
    got = dbm_to_watt(e.layers["interference_dbm"])
    served = e.layers["serving_station"] >= 0
    np.testing.assert_allclose(got[served], expected[served], rtol=1e-9)
    assert set(np.unique(e.layers["serving_station"][served])) == {3}       # only BS-04 is on 3.5 GHz


def test_an_overlapping_carrier_without_traces_makes_the_evaluation_wait_for_them(ctx):
    st = network_of(ctx)
    nr, shifted = presets(ctx)["nr_3500"], custom(ctx, "nr_3500", 3.55e9, 100e6)
    b = replace(st[1], carriers=(ws.StationCarrier.of(st[1], shifted["id"]),))
    stations = [st[0], b, st[2], st[3]]
    maps = cache_for(ctx, stations, [nr])                           # the shifted carrier is not traced
    with pytest.raises(ws.MissingTraces):
        ws.evaluate(ctx, stations, nr, ws.RadioSettings.baseline(ctx), maps.get, carriers=[nr, shifted])
    needs = ws.evaluation_jobs(ws.jobs(ctx, stations, [nr, shifted]), [nr, shifted], nr["id"])
    assert {sj.job.frequency_hz for sj in needs} == {3.5e9, 3.55e9}


def test_serving_stations_are_numbered_over_all_enabled_stations(ctx):
    st = network_of(ctx)
    carriers = [presets(ctx)[c] for c in THREE]
    maps = cache_for(ctx, st, carriers)
    e = ws.evaluate(ctx, st, presets(ctx)["nr_3500"], ws.RadioSettings.baseline(ctx), maps.get, carriers=carriers)
    assert e.station_ids == ["S1", "S2", "S3", "S4"]
    assert set(np.unique(e.layers["serving_station"])) <= {-1, 1, 3}
    assert {sid for sid, _ in e.sectors} == {"S2", "S4"}
    assert e.summary["served_share_per_site"][0] == 0.0 and e.summary["served_share_per_site"][2] == 0.0


def test_a_carrier_no_station_transmits_cannot_be_evaluated(ctx):
    st = network_of(ctx)
    with pytest.raises(ws.NoTransmitter):
        ws.evaluate(ctx, st, presets(ctx)["c6g_15000"], ws.RadioSettings.baseline(ctx), {}.get)


# ---------------------------------------------------------------- by generation
def test_generations_of_the_presets():
    assert [ws.generation({"preset": p}) for p in ("lte_1800", "nr_3500", "nr_28000", "c6g_8000", "c6g_15000")] == \
        ["4g", "5g", "5g", "6g", "6g"]


def test_results_by_generation_take_the_best_carrier_of_the_generation(ctx):
    st = network_of(ctx)
    d = replace(st[3], carriers=(*st[3].carriers, ws.StationCarrier.of(st[3], "nr_28000")))
    stations = [*st[:3], d]
    carriers = [presets(ctx)[c] for c in (*THREE, "nr_28000")]
    maps = cache_for(ctx, stations, carriers)
    radio = ws.RadioSettings.baseline(ctx)
    ev = {c["id"]: ws.evaluate(ctx, stations, c, radio, maps.get, carriers=carriers) for c in carriers}
    gen = ws.by_generation(ctx, ev, carriers)
    assert set(gen) == {"4g", "5g", "6g"} and gen["5g"].carriers == ["nr_3500", "nr_28000"]
    best = np.fmax(ev["nr_3500"].layers["sinr_db"], ev["nr_28000"].layers["sinr_db"])
    np.testing.assert_array_equal(gen["5g"].layers["sinr_db"], best)
    pick = gen["5g"].layers["serving_carrier"]
    out = ctx.exp.outdoor
    np.testing.assert_array_equal(gen["5g"].layers["serving_station"][out & (pick == 1)],
                                  ev["nr_28000"].layers["serving_station"][out & (pick == 1)])
    cov = gen["5g"].summary["coverage_fraction"]
    assert cov >= max(ev["nr_3500"].summary["coverage_fraction"], ev["nr_28000"].summary["coverage_fraction"])
    np.testing.assert_array_equal(gen["4g"].layers["sinr_db"], ev["lte_1800"].layers["sinr_db"])


# ---------------------------------------------------------------- saving, classification
def test_a_station_round_trips_with_its_carriers(ctx):
    for s in network_of(ctx):
        assert ws.Station.from_dict(asdict(s)) == s
    legacy = asdict(ws.place(ctx, -40, -40, template(ctx), []))
    legacy.pop("carriers")                                          # experiments saved before this change
    assert ws.Station.from_dict(legacy).carriers is None


def test_stations_with_their_own_carriers_make_a_custom_experiment_and_say_how(ctx):
    st = network_of(ctx)
    c = ws.classify(ctx, st, ws.RadioSettings.baseline(ctx), [presets(ctx)[x] for x in THREE])
    assert c.configuration == cl.CUSTOM
    text = " ".join(c.deviations)
    assert "S1 carriers: lte_1800" in text and "S2 nr_3500: tx_power_dbm = 40" in text
    assert "S4 c6g_8000: downtilt_deg = 4" in text


# ---------------------------------------------------------------- carriers renamed, removed, reassigned
def test_station_carriers_follow_a_carrier_whose_id_changes(ctx):
    st = network_of(ctx)
    moved = ws.rename_carrier(st, "nr_3500", "nr_3500.f3600b100")
    assert [e.carrier_id for e in moved[1].carriers] == ["nr_3500.f3600b100"]
    assert [e.carrier_id for e in moved[3].carriers] == ["lte_1800", "nr_3500.f3600b100", "c6g_8000"]
    assert moved[0] == st[0]


def test_removing_a_carrier_removes_it_from_every_station(ctx):
    st = network_of(ctx)
    kept = ws.without_carrier(st, "c6g_8000")
    assert kept[2].carriers == () and [e.carrier_id for e in kept[3].carriers] == ["lte_1800", "nr_3500"]


def test_a_station_can_be_given_a_set_of_carriers_with_its_own_values(ctx):
    s = ws.place(ctx, -40, -40, template(ctx), [])
    six = ws.with_carriers(s, ["c6g_8000", "c6g_15000"])
    assert [e.carrier_id for e in six.carriers] == ["c6g_8000", "c6g_15000"]
    assert all(e.tx_power_dbm == s.tx_power_dbm and e.downtilt_deg == s.downtilt_deg for e in six.carriers)
    d = network_of(ctx)[3]                                          # values of its first carrier that is on
    assert ws.with_carriers(d, ["c6g_15000"]).carriers[0] == replace(d.carriers[0], carrier_id="c6g_15000")


# ---------------------------------------------------------------- the saved run of a mixed network
def written_mixed_run(ctx, tmp_path):
    from bns.app import run_record

    st = network_of(ctx)
    carriers = [{**presets(ctx)[c], "selected": True} for c in THREE]
    maps = cache_for(ctx, st, carriers)
    radio = ws.RadioSettings.baseline(ctx)
    ev = {c["id"]: ws.evaluate(ctx, st, c, radio, maps.get, carriers) for c in carriers}
    more = {c["id"]: run_record.extras(ctx, st, c, radio, maps.get, 0.9, carriers) for c in carriers}
    jobs = ws.jobs(ctx, st, carriers)
    records = [{"scenario": c["id"], "site": st[sj.station].station_id, "key": sj.job.key(), "trace_seconds": 1.0}
               for c in carriers for sj in jobs[c["id"]]]
    config = {"experiment_id": "exp-mixed", "name": "Mixed", "radio": asdict(radio),
              "stations": [asdict(s) for s in st], "carriers": carriers}
    out = run_record.write(tmp_path, ctx, config, st, carriers, radio, ev, more, job_records=records,
                           workload={"jobs": len(records), "cached": len(records), "to_trace": 0}, timing={},
                           versions={}, target=0.9, network_carriers=carriers)
    return out, st, carriers, ev, maps


def test_a_mixed_run_records_each_stations_carriers_and_results_by_generation(ctx, tmp_path):
    from bns.app import results

    out, st, carriers, ev, _ = written_mixed_run(ctx, tmp_path)
    r = results.load_run(out)
    by_id = {s["station_id"]: s for s in r.manifest["stations"]}
    assert set(by_id["S1"]["carrier_antennas"]) == {"lte_1800"}
    assert set(by_id["S4"]["carrier_antennas"]) == set(THREE)
    assert by_id["S2"]["carrier_antennas"]["nr_3500"]["tx_power_dbm"] == 40.0
    res = r.summary["results"]
    assert res["nr_3500"]["sites_alone"][0] is None and res["nr_3500"]["sites_alone"][1] is not None
    assert [g["sites"] for g in res["nr_3500"]["grown_in_given_order"]] == [[2], [2, 4]]
    assert set(r.summary["generations"]) == {"4g", "5g", "6g"}
    np.testing.assert_array_equal(r.layer("nr_3500", "sinr_db"), ev["nr_3500"].layers["sinr_db"])
    assert r.classification.configuration == cl.CUSTOM
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "S1 " in md and "carriers lte_1800 [" in md and "nr_3500 [40 dBm" in md and "By generation" in md


def test_a_mixed_run_reopens_with_every_station_and_carrier_and_shows_its_results(ctx, tmp_path):
    from bns.app import results

    out, st, carriers, ev, maps = written_mixed_run(ctx, tmp_path)
    m = results.load_run(out).manifest
    again, check = ws.stations_from_run(ctx, m)
    assert [replace(s, source_run=None) for s in again] == st and check["exact"]
    assert [c["id"] for c in ws.design_carriers(m, ws.preset_carriers(ctx))] == list(THREE)
    shown = ws.evaluation_from_run(ctx, st, carriers[1], ws.RadioSettings.baseline(ctx), out, carriers)
    np.testing.assert_array_equal(shown.layers["sinr_db"], ev["nr_3500"].layers["sinr_db"])
    np.testing.assert_array_equal(shown.layers["serving_station"], ev["nr_3500"].layers["serving_station"])
    other = [st[0], replace(st[1], carriers=(replace(st[1].carriers[0], tx_power_dbm=43.0),)), *st[2:]]
    assert ws.evaluation_from_run(ctx, other, carriers[1], ws.RadioSettings.baseline(ctx), out, carriers) is None


def test_a_carrier_added_to_a_station_starts_from_its_own_carrier_values(ctx):
    st = network_of(ctx)
    c = st[2]                                                       # its 6G carrier: bearing 30 degrees
    added = ws.new_carrier(c, "nr_3500.f3550b100")
    assert added == replace(c.carriers[0], carrier_id="nr_3500.f3550b100")
    legacy = ws.place(ctx, -40, -40, template(ctx), [])
    assert ws.new_carrier(legacy, "lte_1800", enabled=False) == ws.StationCarrier.of(legacy, "lte_1800", enabled=False)
