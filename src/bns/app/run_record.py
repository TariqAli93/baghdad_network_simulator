"""Write a completed workspace simulation as a run in the existing multi-site format (no UI code).

The run folder holds what scripts/run_multi_site.py writes (manifest.json, summary.json, network.npz,
summary.md, cells_<scenario>.csv, sites.geojson, figures), so the history, the comparison pages and the
reports read it like any run. Additions: "source": "workspace", the experiment it came from with a
copy of the executed configuration, every station with its own antennas, the carriers (preset or
custom) and the placement in the classification. Runs are never rewritten: each run is a new folder.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from bns.app import carriers as ca
from bns.app import workspace as ws
from bns.simulation import experiment as ex

MAP_KEYS = ("path_gain_db", "rx_power_dbm", "sinr_db", "rate_bps", "covered", "serving_site", "serving_sector",
            "interference_dbm")
SUMMARY_KEYS = ("coverage_fraction", "unreached_fraction", "sinr_db_median", "sinr_db_p5", "rate_median_bps",
                "rate_p5_bps", "rx_power_dbm_median", "interference_limited_share",
                "interference_over_noise_db_median", "served_share_per_site")


def site_record(ctx: ws.Context, s: ws.Station) -> dict:
    b = ctx.building(s.building_id) if s.building_id else None
    return {"candidate_id": s.station_id, "x": s.x, "y": s.y, "z": s.antenna_height_m,
            "building_id": s.building_id or "", "roof_height_m": s.roof_height_m if s.roof_height_m is not None else 0.0,
            "footprint_area_m2": float(b.polygon.area) if b is not None else None,
            "height_category": s.height_category or "hypothetical", "mount": s.mount,
            "tx_power_dbm": s.tx_power_dbm, "pattern": s.pattern, "sectors": s.sectors,
            "azimuth_deg": s.azimuth_deg, "downtilt_deg": s.downtilt_deg, "origin": s.origin}


def extras(ctx: ws.Context, stations: list[ws.Station], carrier: dict, radio: ws.RadioSettings, load,
           target: float) -> dict:
    """What run_multi_site.py reports beside the network: every station alone, the network grown in the
    given order, the additions that lowered coverage and the interference-aware SINR greedy."""
    on = [s for s in stations if s.enabled]

    def summary_of(keep):
        e = ws.evaluate(ctx, [replace(s, enabled=i in keep) for i, s in enumerate(on)], carrier, radio, load)
        return {k: e.summary[k] for k in SUMMARY_KEYS}, e

    alone = [summary_of({i}) for i in range(len(on))]
    grown = [summary_of(set(range(n)))[0]["coverage_fraction"] for n in range(1, len(on) + 1)]
    g = ws.greedy(ctx, on, carrier, radio, load, target=target)
    return {
        "sites_alone": [a for a, _ in alone],
        "alone_sinr": [e.layers["sinr_db"] for _, e in alone],
        "grown_in_given_order": [{"sites": list(range(1, n + 1)), "coverage_fraction": v}
                                 for n, v in enumerate(grown, start=1)],
        "additions_that_lowered_coverage": [{"added_site": n + 1, "change": grown[n] - grown[n - 1]}
                                            for n in range(1, len(grown)) if grown[n] < grown[n - 1]],
        "greedy_sinr": {"selected_sites": [i + 1 for i in g.selected], "coverage_after": g.coverage_after,
                        "target": target, "target_reached": g.target_reached, "stopped_because": g.stopped_because,
                        "degrading_additions": [{**d, "candidate": d["candidate"] + 1} for d in g.degrading_additions],
                        "note": "greedy heuristic over these stations only; not a proven minimum"},
    }


def _figures(out: Path, ctx: ws.Context, on: list[ws.Station], carriers: list[dict], evaluations: dict,
             label: str) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    from bns.reporting import plotstyle as style

    style.apply()
    grid, outdoor = ctx.exp.grid, ctx.exp.outdoor
    half = grid.cell_size_m / 2
    extent = [grid.x_centers[0] - half, grid.x_centers[-1] + half, grid.y_centers[0] - half, grid.y_centers[-1] + half]
    n = len(carriers)

    def mark(ax):
        for s in on:
            ax.plot(s.x, s.y, marker="^" if s.mount == ws.ROOFTOP else "D", color=style.INK, markersize=6,
                    linestyle="none", markerfacecolor=style.INK if s.mount == ws.ROOFTOP else "white")
            ax.annotate(s.station_id, (s.x, s.y), xytext=(4, 4), textcoords="offset points", fontsize=7)

    def title(c):
        return f"{c['label']}{' (custom)' if c.get('custom') else ''}\n{c['frequency_hz'] / 1e9:g} GHz, " \
               f"{c['bandwidth_hz'] / 1e6:g} MHz"

    names = []
    for key, heading, vmin, vmax, unit in (("sinr_db", "SINR, all stations and sectors on one carrier", -10, 40, "dB"),
                                           ("interference_dbm", "Interference power (all non-serving sectors)",
                                            -130, -50, "dBm")):
        fig, axes = plt.subplots(1, n, figsize=(3.9 * n, 4.4), sharey=True, squeeze=False)
        for ax, c in zip(axes[0], carriers, strict=True):
            colours = style.SEQUENTIAL.with_extremes(under=style.SURFACE)
            im = ax.imshow(np.where(outdoor, evaluations[c["id"]].layers[key], np.nan), origin="lower", extent=extent,
                           cmap=colours, vmin=vmin, vmax=vmax)
            mark(ax)
            ax.set_title(title(c), fontsize=9)
            ax.grid(False)
            ax.set_xlabel("x [m]")
        axes[0][0].set_ylabel("y [m]")
        fig.colorbar(im, ax=list(axes[0]), label=unit, shrink=0.85, extend="min")
        fig.suptitle(f"{heading}  |  {label}", x=0.05, ha="left", fontsize=11, fontweight="bold")
        fig.savefig(out / f"network_{key}.png")
        plt.close(fig)
        names.append(f"network_{key}.png")

    colours = ListedColormap(["#2a6f97", "#c0504d", "#5b8c3a", "#8064a2", "#d08c2b", "#4b9b9b", "#7a6a53",
                              "#b5527a"][:max(len(on), 1)])
    fig, axes = plt.subplots(1, n, figsize=(3.9 * n, 4.4), sharey=True, squeeze=False)
    for ax, c in zip(axes[0], carriers, strict=True):
        m = evaluations[c["id"]].layers["serving_station"].astype(float)
        ax.imshow(np.where(outdoor & (m >= 0), m, np.nan), origin="lower", extent=extent, cmap=colours,
                  vmin=-0.5, vmax=len(on) - 0.5, interpolation="nearest")
        mark(ax)
        ax.set_title(title(c), fontsize=9)
        ax.grid(False)
    fig.suptitle(f"Serving station (strongest sector)  |  {label}", x=0.05, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(out / "serving_site.png")
    plt.close(fig)
    names.append("serving_site.png")
    return names


def write(root: Path, ctx: ws.Context, experiment: dict, stations: list[ws.Station], carriers: list[dict],
          radio: ws.RadioSettings, evaluations: dict, more: dict, *, job_records: list[dict], workload: dict,
          timing: dict, versions: dict, target: float, mode: str = "development") -> Path:
    """Write the run folder and return it. `evaluations` and `more` are keyed by carrier id."""
    from bns import runtime
    from bns.reporting import export
    from bns.simulation.cache import scene_fingerprint
    from bns.simulation.setup import scene_azimuth_to_bearing_deg

    exp = ctx.exp
    on = [s for s in stations if s.enabled]
    c = ws.classify(ctx, stations, radio, carriers)
    label = c.label
    run_id = (f"multi_site-{exp.area.name}-{exp.variant}-{exp.profile.name}-{len(on)}sites-ws-"
              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out = Path(root) / "outputs" / "runs" / mode / run_id
    out.mkdir(parents=True)

    arrays = {"x": exp.grid.x_centers, "y": exp.grid.y_centers, "outdoor": exp.outdoor}
    for car in carriers:
        sid, e = car["id"], evaluations[car["id"]]
        layers = {**e.layers, "serving_site": e.layers["serving_station"]}
        arrays.update({f"{sid}_{k}": layers[k] for k in (*MAP_KEYS, "rate_3gpp_bps") if k in layers})
        arrays.update({f"{sid}_alone{n}_sinr_db": a for n, a in enumerate(more[sid]["alone_sinr"])})
    np.savez_compressed(out / "network.npz", **arrays)

    transformer = exp.area.transformer()
    for car in carriers:
        e = evaluations[car["id"]]
        export.cells_csv(out / f"cells_{car['id']}.csv", exp.grid, transformer, exp.outdoor,
                         {**{k: ({**e.layers, "serving_site": e.layers["serving_station"]})[k] for k in MAP_KEYS
                             if k != "rate_bps"}, "rate_mbps": e.layers["rate_bps"] / 1e6}, label)
    sites = [site_record(ctx, s) for s in on]
    export.sites_geojson(out / "sites.geojson", transformer, [SimpleNamespace(**r) for r in sites], label)
    figures = _figures(out, ctx, on, carriers, evaluations, label)

    first = ws.antennas(on[0], exp.config.polarization)
    radio_overrides = ws.radio_overrides(ctx, radio)
    system = ex.custom_radio_system(exp.system, radio_overrides) if radio_overrides else exp.system
    overrides = {**exp.overrides, **radio_overrides}
    q = exp.quality
    manifest = {
        "label": label, "run_id": run_id, "kind": "multi_site", "mode": mode, "source": "workspace",
        "experiment": {"id": experiment.get("experiment_id"), "name": experiment.get("name"), "config": experiment},
        "run_class": c.configuration, "overrides": overrides, "classification": c.as_dict(),
        "backend": {"name": exp.backend, "note": exp.backend_note, "variant": ctx.engine["variant"],
                    "status": (exp.config.backends or {}).get(exp.backend, {}).get("status"),
                    "gpu": runtime.gpu_description() if exp.backend == "gpu" else None},
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "area": {"name": exp.area.name, "role": exp.area.role, "approved": exp.area.approved, "variant": exp.variant,
                 "osm_snapshot_sha256": q.get("osm_snapshot_sha256"), "scene_fingerprint": scene_fingerprint(exp.scene_dir),
                 "height_categories_percent": (q.get("height_categories") or {}).get("by_count_percent"),
                 "height_model": ({k: (q.get("height_model") or {}).get(k) for k in ("name", "kind", "seed")}
                                  | {"synthetic": ((q.get("height_model") or {}).get("synthetic") or {})
                                     .get("synthetic_percent")}) if q.get("height_model") else None,
                 "fit_for_research": q.get("fit_for_research")},
        "site_rule": {"workspace": True, "placement": c.placement, **exp.candidate_rule},
        "sites": sites,
        "stations": [{**asdict(s), "antennas": [asdict(a) for a in ws.antennas(s, exp.config.polarization)],
                      "sector_bearings_deg": list(s.bearings_deg)} for s in on],
        "sectors_per_site": [asdict(a) for a in first],
        "sector_bearings_deg": [scene_azimuth_to_bearing_deg(a.orientation_rad[0]) for a in first],
        "azimuth_convention": "orientation_rad[0]: yaw counter-clockwise from east (scene x east, y north); "
                              "sector_bearings_deg: compass, clockwise from north",
        "antenna_rule": exp.site_rule,
        "sector_positions_m": {s.station_id: ws.sector_positions(ctx, s, ws.antennas(s, exp.config.polarization))
                               for s in on},
        "profile": asdict(exp.profile), "grid": asdict(exp.grid), "mechanisms": asdict(exp.config.mechanisms),
        "seeds": list(exp.config.seeds),
        "radio_parameters": system.status_report(ex.USED + ["coverage_target", "frequency_reuse"]),
        "atmosphere": {"baseline": asdict(exp.baseline), "rain_rate_mm_h": radio.rain_rate_mm_h,
                       "gas": {car["id"]: car.get("gas", "tabulated") for car in carriers},
                       "gas_db_per_km": {car["id"]: ca.gas_db_per_km({"gas": ca.TABULATED, **car})
                                         if exp.baseline.include_gas else 0.0 for car in carriers},
                       "gas_models": {car["id"]: car["gas_model"] for car in carriers if car.get("gas_model")}},
        "scenarios": carriers, "workload_before_run": workload, "jobs": job_records, "timing": timing,
        "versions": versions, "figures": figures,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str, ensure_ascii=False),
                                       encoding="utf-8")
    results = {car["id"]: {"network": {**evaluations[car["id"]].summary},
                           **{k: v for k, v in more[car["id"]].items() if k != "alone_sinr"}} for car in carriers}
    (out / "summary.json").write_text(json.dumps({"label": label, "results": results}, indent=2, default=str),
                                      encoding="utf-8")
    lines = [f"# {label}", "", f"## Workspace simulation {run_id}", "",
             f"Experiment: {experiment.get('name')} ({experiment.get('experiment_id')}). "
             f"Placement: {c.placement or 'not recorded'}." + (f" Deviations: {'; '.join(c.deviations)}." if c.deviations
                                                              else ""), "",
             "- Stations (" + str(len(on)) + "): " + "; ".join(
                 f"{s.station_id} {s.mount}" + (f" on {s.building_id} (roof {s.roof_height_m:g} m)" if s.building_id else "")
                 + f", antenna {s.antenna_height_m:g} m at ({s.x:.0f}, {s.y:.0f}), {s.tx_power_dbm:g} dBm, "
                 f"{len(s.bearings_deg) or 1} sector(s) {'/'.join(f'{b:g}' for b in s.bearings_deg) or 'iso'}°, "
                 f"tilt {s.downtilt_deg:g}°" for s in on),
             f"- Profile {exp.profile.name}: {exp.profile.cell_size_m:g} m cells, {exp.profile.rays_per_site:.0e} rays "
             f"per sector; {int(exp.outdoor.sum())} outdoor cells; backend {exp.backend.upper()}.", "",
             "| Carrier | Coverage | Median SINR | 5th-pct rate | Median rate | Mapped 5th-pct rate | "
             "Interference-limited | Greedy (SINR) |", "|---|---|---|---|---|---|---|---|"]
    for car in carriers:
        s_, g = evaluations[car["id"]].summary, more[car["id"]]["greedy_sinr"]
        mapped = s_.get("rate_3gpp_p5_bps")
        lines.append(f"| {car['label']} {car['frequency_hz'] / 1e9:g} GHz / {car['bandwidth_hz'] / 1e6:g} MHz"
                     f"{' (custom)' if car.get('custom') else ''} | {100 * s_['coverage_fraction']:.1f} % | "
                     f"{s_['sinr_db_median']:.1f} dB | {s_['rate_p5_bps'] / 1e6:.1f} Mbit/s | "
                     f"{s_['rate_median_bps'] / 1e6:.0f} Mbit/s | "
                     f"{'—' if mapped is None else f'{mapped / 1e6:.1f} Mbit/s'} | "
                     f"{100 * s_['interference_limited_share']:.0f} % | stations {g['selected_sites']} -> "
                     f"{100 * g['coverage_after'][-1]:.1f} % ({g['stopped_because']}) |")
    lines += ["", f"Trace time {timing.get('trace_wall_seconds', 0):.0f} s for {workload.get('to_trace', 0)} new traces "
              f"({workload.get('cached', 0)} of {workload.get('jobs', 0)} were cached); total "
              f"{timing.get('total_wall_seconds', 0):.0f} s.", "",
              "Shannon rates are theoretical upper bounds for one user with the whole carrier. Candidate 6G carriers "
              "are research assumptions, not finalised standards; their rate mapping is an NR-based approximation. "
              "The greedy result is a heuristic over these stations only."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
