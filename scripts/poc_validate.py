"""Phase 0 validation experiments. Path gain only: no transmit power, noise or thresholds.

    uv run python scripts/poc_validate.py e1 e2 e3      (or: all)

Each experiment runs in a fresh worker process and its output is kept only if
that process exits cleanly (see bns.runtime.run_isolated). Results land in
outputs/runs/phase0/<experiment>/ as result.json plus figures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

from bns import runtime
from bns.core.units import free_space_path_gain, linear_to_db, wavelength

ROOT = runtime.PROJECT_ROOT
# BNS_PHASE0_OUT redirects the records (the engine tests use a temporary folder so the
# committed Phase 0 records are never overwritten).
OUT = Path(os.environ["BNS_PHASE0_OUT"]) if os.environ.get("BNS_PHASE0_OUT") else ROOT / "outputs" / "runs" / "phase0"
SCENES = ROOT / "data" / "scenes"

# Provisional acceptance tolerances (to be approved by the supervisor).
TOL = {
    "analytic_max_abs_db": 0.25,   # worst cell vs closed form (E1, E2)
    "analytic_rms_db": 0.05,       # RMS over all cells vs closed form (E1, E2)
    "diffraction_db": 2.0,         # E3 shadow-boundary and frequency-scaling checks
}
SAMPLES = 10**7                    # rays per site for the analytic checks
# Rays leave the site on a fixed lattice, so the error of a cell falls with the
# number of rays that reach it. E2 uses 5 m cells (a quarter of E1's cell area)
# and reaches further out, hence ten times more rays for the same tolerance.
E2_SAMPLES = 10**8


def scenarios() -> list[dict]:
    data = yaml.safe_load((ROOT / "configs" / "scenarios.yaml").read_text(encoding="utf-8"))
    for sc in data["scenarios"]:
        # YAML reads "1.8e9" as text; convert explicitly so a typo cannot pass silently.
        sc["frequency_hz"] = float(sc["frequency_hz"])
        sc["bandwidth_hz"] = float(sc["bandwidth_hz"])
    return sorted(data["scenarios"], key=lambda s: s["frequency_hz"])


def error_stats(measured, reference, mask=None) -> dict:
    err = linear_to_db(measured / reference)
    if mask is not None:
        err = err[mask]
    return {"mean_db": float(err.mean()), "rms_db": float(np.sqrt((err**2).mean())),
            "max_abs_db": float(np.abs(err).max())}


# --- E1 free space ------------------------------------------------------------------


def e1_free_space(out: Path) -> dict:
    """Empty scene: the map must equal the Friis formula averaged over each cell."""
    from bns.propagation.sionna_engine import Grid, Propagation, open_scene, path_gain_map
    from bns.reporting import plotstyle as style
    from bns.validation.analytic import cell_averaged_friis
    import matplotlib.pyplot as plt

    grid = Grid((0.0, 0.0), (400.0, 200.0), 10.0)
    tx = (30.0, -20.0, 25.0)   # off-centre on purpose: a swapped x/y axis would show
    los_only = Propagation(max_depth=0, specular_reflection=False)

    def reference(f):
        return cell_averaged_friis(tx, grid.x_centers, grid.y_centers,
                                   grid.height_m, grid.cell_size_m, f)

    bands, maps = [], {}
    for sc in scenarios():
        f = sc["frequency_hz"]
        scene = open_scene(None, f)
        res = path_gain_map(scene, tx, grid, los_only, SAMPLES, [1])
        stats = error_stats(res.mean, reference(f))
        bands.append({"scenario": sc["id"], "frequency_hz": f, **stats,
                      "seconds": round(res.seconds_per_seed[0], 3)})
        maps[sc["id"]] = linear_to_db(res.mean / reference(f))

    f_mid = 3.5e9
    scene = open_scene(None, f_mid)
    convergence = []
    for n in (10**5, 10**6, 10**7, 10**8):
        res = path_gain_map(scene, tx, grid, los_only, n, [1])
        convergence.append({"samples": n, **error_stats(res.mean, reference(f_mid)),
                            "seconds": round(res.seconds_per_seed[0], 3)})

    two = path_gain_map(scene, tx, grid, los_only, 10**6, [1, 2], keep_per_seed=True)
    seed_rel_diff = float(np.max(np.abs(two.per_seed[0] - two.per_seed[1]) / two.per_seed[0]))

    iy, ix = np.unravel_index(np.argmax(two.mean), two.mean.shape)
    orientation_ok = bool(ix == np.argmin(np.abs(grid.x_centers - tx[0]))
                          and iy == np.argmin(np.abs(grid.y_centers - tx[1])))

    passed = bool(orientation_ok and all(
        b["max_abs_db"] <= TOL["analytic_max_abs_db"] and b["rms_db"] <= TOL["analytic_rms_db"]
        for b in bands))

    style.apply()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.6), width_ratios=[1.5, 1])
    extent = [grid.x_centers[0] - 5, grid.x_centers[-1] + 5,
              grid.y_centers[0] - 5, grid.y_centers[-1] + 5]
    lim = TOL["analytic_max_abs_db"]
    im = ax1.imshow(maps["nr_3500"], origin="lower", extent=extent, cmap=style.DIVERGING,
                    vmin=-lim, vmax=lim)
    ax1.plot(tx[0], tx[1], marker="^", color=style.INK, markersize=7, linestyle="none")
    ax1.annotate("site", (tx[0], tx[1]), xytext=(6, 6), textcoords="offset points", fontsize=9)
    ax1.set(title="Ray tracer minus Friis, 3.5 GHz, 10 million rays",
            xlabel="x [m]", ylabel="y [m]")
    ax1.grid(False)
    fig.colorbar(im, ax=ax1, label="error [dB]", shrink=0.85)
    ns = [c["samples"] for c in convergence]
    ax2.loglog(ns, [c["max_abs_db"] for c in convergence], marker="o",
               color=style.SCENARIO_COLORS["nr_3500"])
    ax2.axhline(lim, color=style.NEUTRAL_SERIES, linestyle="--", linewidth=1.2)
    ax2.annotate("tolerance", (ns[0], lim), xytext=(0, 4), textcoords="offset points",
                 fontsize=9, color=style.INK_SECONDARY)
    ax2.set(title="Worst-cell error vs rays", xlabel="rays per site", ylabel="max |error| [dB]")
    fig.savefig(out / "e1_free_space.png")
    plt.close(fig)

    return {"experiment": "E1 free space", "passed": passed, "grid": grid.shape, "tx": tx,
            "samples": SAMPLES, "bands": bands, "convergence_3p5ghz": convergence,
            "seed_max_relative_difference": seed_rel_diff, "orientation_ok": orientation_ok}


# --- E2 ground reflection -----------------------------------------------------------


def e2_ground_reflection(out: Path) -> dict:
    """Flat concrete ground: direct + reflected power against the Fresnel slab formula."""
    from bns.geospatial.osm_scene import SceneSettings, write_scene
    from bns.propagation.sionna_engine import Grid, Propagation, open_scene, path_gain_map
    from bns.reporting import plotstyle as style
    from bns.validation import analytic as an
    import matplotlib.pyplot as plt

    settings = SceneSettings()
    scene_dir = SCENES / "poc_ground"
    write_scene(scene_dir, [], settings, (300.0, 300.0))
    grid = Grid((0.0, 0.0), (400.0, 400.0), 5.0)
    h_t, h_r = 25.0, grid.height_m
    tx = (0.0, 0.0, h_t)
    xs, ys = grid.x_centers, grid.y_centers
    rho_cells = np.hypot(*np.meshgrid(xs, ys))
    edges = np.arange(10.0, 205.0, 5.0)
    centres = 0.5 * (edges[:-1] + edges[1:])
    bin_of = np.digitize(rho_cells, edges) - 1

    def radial(values):
        return np.array([values[bin_of == i].mean() for i in range(len(centres))])

    rows, profiles = [], {}
    for sc in scenarios():
        f = sc["frequency_hz"]
        eta = an.itu_concrete_permittivity(f)
        lam = wavelength(f)
        friis = an.cell_averaged_friis(tx, xs, ys, h_r, grid.cell_size_m, f)
        spreading = an.cell_average(
            lambda x, y: (lam / (4 * np.pi)) ** 2 / (x**2 + y**2 + (h_t + h_r) ** 2),
            xs, ys, grid.cell_size_m)
        for pol, mode in (("V", "TM"), ("H", "TE")):
            ref_total = an.cell_average(
                lambda x, y: an.two_ray_noncoherent_gain(
                    np.hypot(x, y), h_t, h_r, f, eta, settings.ground_thickness_m, mode),
                xs, ys, grid.cell_size_m)
            scene = open_scene(scene_dir / "scene.xml", f, polarization=pol)
            total = path_gain_map(scene, tx, grid, Propagation(max_depth=1), E2_SAMPLES, [1])
            refl = path_gain_map(scene, tx, grid, Propagation(max_depth=1, los=False),
                                 E2_SAMPLES, [1])
            r2_measured = radial(refl.mean / spreading)
            r2_reference = radial((ref_total - friis) / spreading)
            dip = int(np.argmin(r2_measured))
            rows.append({
                "scenario": sc["id"], "frequency_hz": f, "polarization": pol, "fresnel_case": mode,
                **error_stats(total.mean, ref_total),
                "reflectance_max_abs_error": float(np.abs(r2_measured - r2_reference).max()),
                "reflectance_min": float(r2_measured.min()),
                "reflectance_min_at_m": float(centres[dip]),
                "reference_min_at_m": float(centres[int(np.argmin(r2_reference))]),
                "seconds": round(total.seconds_per_seed[0] + refl.seconds_per_seed[0], 3),
            })
            profiles[(sc["id"], pol)] = (r2_measured, r2_reference)

    brewster_m = float(np.sqrt(an._CONCRETE_EPS_R) * (h_t + h_r))
    v_rows = [r for r in rows if r["polarization"] == "V"]
    h_rows = [r for r in rows if r["polarization"] == "H"]
    analytic_ok = all(r["max_abs_db"] <= TOL["analytic_max_abs_db"]
                      and r["rms_db"] <= TOL["analytic_rms_db"] for r in rows)
    dip_ok = all(r["reflectance_min"] < 0.02
                 and abs(r["reflectance_min_at_m"] - r["reference_min_at_m"]) <= 5.0
                 for r in v_rows)
    no_dip_ok = all(r["reflectance_min"] > 0.1 for r in h_rows)
    passed = bool(analytic_ok and dip_ok and no_dip_ok)

    style.apply()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    # The five bands lie on top of each other (concrete's permittivity barely
    # changes with frequency), so one band is drawn and the spread is stated.
    shown = "nr_3500"
    spread = max(float(np.abs(profiles[(sc["id"], pol)][0] - profiles[(shown, pol)][0]).max())
                 for sc in scenarios() for pol in ("V", "H"))
    for ax, pol, title in ((axes[0], "V", "Vertical polarisation (TM): Brewster dip"),
                           (axes[1], "H", "Horizontal polarisation (TE): no dip")):
        measured, reference = profiles[(shown, pol)]
        ax.plot(centres, reference, color=style.NEUTRAL_SERIES, linewidth=1.2, linestyle="--")
        ax.plot(centres, measured, color=style.SCENARIO_COLORS[shown], linestyle="none",
                marker="o", markersize=4)
        ax.set(title=title, xlabel="ground distance from site [m]")
    axes[0].set_ylabel("ground reflectance (power)")
    axes[0].axvline(brewster_m, color=style.AXIS, linewidth=1)
    axes[0].annotate(f"Brewster distance {brewster_m:.0f} m", (brewster_m, 0.7),
                     xytext=(6, 0), textcoords="offset points", fontsize=9,
                     color=style.INK_SECONDARY)
    axes[1].annotate("dots: ray tracer at 3.5 GHz\ndashes: Fresnel slab formula\n"
                     f"other bands differ by at most {spread:.3f}",
                     (0.97, 0.06), xycoords="axes fraction", ha="right", va="bottom",
                     fontsize=9, color=style.INK_SECONDARY)
    fig.savefig(out / "e2_ground_reflection.png")
    plt.close(fig)

    return {"experiment": "E2 ground reflection", "passed": passed,
            "checks": {"matches_slab_formula": bool(analytic_ok),
                       "brewster_dip_for_vertical": bool(dip_ok),
                       "no_dip_for_horizontal": bool(no_dip_ok)},
            "site_height_m": h_t, "receiver_height_m": h_r,
            "ground_thickness_m": settings.ground_thickness_m,
            "brewster_distance_m": brewster_m, "samples": E2_SAMPLES, "rows": rows}


# --- E3 diffraction -----------------------------------------------------------------


def e3_diffraction(out: Path) -> dict:
    """One long concrete block: field in its shadow against knife-edge theory."""
    from shapely.geometry import box
    from bns.geospatial.osm_scene import HEIGHT_ASSUMED, Building, SceneSettings, write_scene
    from bns.propagation.sionna_engine import Grid, Propagation, open_scene, path_gain_map
    from bns.reporting import plotstyle as style
    from bns.validation import analytic as an
    import matplotlib.pyplot as plt

    settings = SceneSettings()
    scene_dir = SCENES / "poc_block"
    edge_x, edge_z = 5.0, 20.0
    block = Building(box(-edge_x, -300.0, edge_x, 300.0), edge_z, HEIGHT_ASSUMED, (0,))
    meta = write_scene(scene_dir, [block], settings, (320.0, 320.0), with_ground=False)

    tx = (-60.0, 0.0, 30.0)    # above the roof, so the far roof edge is the only wedge in view
    grid = Grid((150.0, 0.0), (300.0, 40.0), 2.0)
    xs, ys, h_r = grid.x_centers, grid.y_centers, grid.height_m
    shadow_boundary_x = edge_x + (edge_x - tx[0]) * (edge_z - h_r) / (tx[2] - edge_z)
    seeds = list(range(1, 9))

    def window(lo, hi):
        return (xs >= lo) & (xs <= hi)

    near = window(shadow_boundary_x - 12.0, shadow_boundary_x - 2.0)
    deep = window(20.0, 60.0)
    lit = window(shadow_boundary_x + 2.0, shadow_boundary_x + 12.0)

    rows, curves = [], {}
    for sc in scenarios():
        f = sc["frequency_hz"]

        def direct_gain(x, y):
            return free_space_path_gain(np.sqrt((x - tx[0]) ** 2 + (y - tx[1]) ** 2
                                                + (h_r - tx[2]) ** 2), f)

        def knife_edge(x, y):
            diffracted, direct = an.edge_path_lengths(tx, (x, y, h_r), edge_x, edge_z)
            nu = an.fresnel_nu(diffracted, direct, f, in_shadow=x < shadow_boundary_x)
            return free_space_path_gain(direct, f) * an.knife_edge_gain(nu)

        friis = an.cell_average(direct_gain, xs, ys, grid.cell_size_m).mean(axis=0)
        reference = an.cell_average(knife_edge, xs, ys, grid.cell_size_m).mean(axis=0)

        scene = open_scene(scene_dir / "scene.xml", f)
        los = path_gain_map(scene, tx, grid, Propagation(max_depth=0, specular_reflection=False),
                            SAMPLES, [1])
        diff = path_gain_map(
            scene, tx, grid,
            Propagation(max_depth=1, los=False, specular_reflection=False, diffraction=True),
            SAMPLES, seeds, keep_per_seed=True)
        measured = diff.mean.mean(axis=0)
        per_seed = diff.per_seed.mean(axis=1)                    # [seed, x]
        rel_noise = per_seed.std(axis=0, ddof=1) / np.sqrt(len(seeds)) / np.maximum(measured, 1e-300)

        excess_measured = -linear_to_db(measured / friis)
        excess_reference = -linear_to_db(reference / friis)
        los_profile = los.mean.mean(axis=0)
        rows.append({
            "scenario": sc["id"], "frequency_hz": f,
            "near_boundary_measured_db": float(excess_measured[near].mean()),
            "near_boundary_knife_edge_db": float(excess_reference[near].mean()),
            "deep_shadow_measured_db": float(excess_measured[deep].mean()),
            "deep_shadow_knife_edge_db": float(excess_reference[deep].mean()),
            "lit_side_step_db": float(linear_to_db(1.0 + measured[lit] / los_profile[lit]).mean()),
            "shadow_cells_without_energy": int(np.sum(measured[window(8.0, shadow_boundary_x - 2)] == 0)),
            "median_relative_noise": float(np.median(rel_noise[deep])),
            "seconds_per_seed": round(float(np.mean(diff.seconds_per_seed[1:])), 3),
        })
        curves[sc["id"]] = (excess_measured, excess_reference)

    base = rows[0]
    for r in rows:
        r["near_boundary_difference_db"] = r["near_boundary_measured_db"] - r["near_boundary_knife_edge_db"]
        r["deep_shadow_difference_db"] = r["deep_shadow_measured_db"] - r["deep_shadow_knife_edge_db"]
        r["scaling_expected_db"] = float(10 * np.log10(r["frequency_hz"] / base["frequency_hz"]))
        r["scaling_measured_db"] = r["deep_shadow_measured_db"] - base["deep_shadow_measured_db"]
    boundary_ok = all(abs(r["near_boundary_difference_db"]) <= TOL["diffraction_db"] for r in rows)
    scaling_ok = all(abs(r["scaling_measured_db"] - r["scaling_expected_db"]) <= TOL["diffraction_db"]
                     for r in rows)

    style.apply()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    shown = (xs > edge_x + 2) & (xs < shadow_boundary_x)   # the shadow region only
    for sc in scenarios():
        measured, reference = curves[sc["id"]]
        colour = style.SCENARIO_COLORS[sc["id"]]
        ax.plot(xs[shown], reference[shown], color=colour, linewidth=1.2, linestyle="--")
        ax.plot(xs[shown], measured[shown], color=colour, label=sc["label"])
    ax.invert_yaxis()
    ax.text(0.98, 0.06, "All curves meet at 6 dB on the shadow boundary (right edge)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            color=style.INK_SECONDARY)
    ax.set(title="Loss behind a 20 m concrete block, relative to free space",
           xlabel="distance behind the block's centre line [m]",
           ylabel="diffraction loss [dB]")
    ax.legend(title="solid: ray tracer   dashed: knife-edge theory", fontsize=8, title_fontsize=8)
    fig.savefig(out / "e3_diffraction.png")
    plt.close(fig)

    return {"experiment": "E3 diffraction", "passed": bool(boundary_ok and scaling_ok),
            "checks": {"shadow_boundary_within_tolerance": bool(boundary_ok),
                       "frequency_scaling_within_tolerance": bool(scaling_ok)},
            "note": ("Knife-edge theory ignores material and polarisation; it is exact only at "
                     "the shadow boundary and an envelope deeper in the shadow."),
            "site": tx, "block_height_m": edge_z, "shadow_boundary_x_m": float(shadow_boundary_x),
            "mesh": meta["mesh"], "samples_per_seed": SAMPLES, "seeds": seeds, "rows": rows}


# --- E4 / E5: the Baghdad block -----------------------------------------------------

BLOCK_SAMPLES = 10**8      # rays per site on the block (justified by E5)
MAST_HEIGHT_M = 3.0        # provisional antenna height above the roof (NOT approved)
FULL_SETTINGS = {"max_depth": 2, "diffraction": True}   # project baseline: 2 reflections + diffraction


def _block_setup():
    """Crop scene, the rooftop site, the receiver grid and the outdoor mask."""
    from bns.geospatial.osm_scene import indoor_mask, load_footprints, rooftop_site
    from bns.propagation.sionna_engine import Grid

    scene_dir = SCENES / "poc_crop"
    if not (scene_dir / "scene.xml").exists():
        raise FileNotFoundError("Run scripts/build_poc_scene.py first.")
    buildings = load_footprints(scene_dir)
    tx, host = rooftop_site(buildings, MAST_HEIGHT_M, within_m=250.0)
    grid = Grid((0.0, 0.0), (400.0, 400.0), 5.0)
    outdoor = ~indoor_mask(buildings, grid.x_centers, grid.y_centers, grid.cell_size_m)
    site = {"position_m": tx, "host_height_m": host.height_m,
            "host_height_source": host.height_source, "mast_height_m": MAST_HEIGHT_M}
    return scene_dir, tx, grid, outdoor, site


def _outdoor_stats(gain, outdoor) -> dict:
    values = gain[outdoor]
    reached = values > 0
    db = linear_to_db(values[reached])
    p5, p50, p95 = np.percentile(db, [5, 50, 95])
    return {"outdoor_cells": int(outdoor.sum()),
            "zero_path_fraction": float(1.0 - reached.mean()),
            "path_gain_p5_db": float(p5), "path_gain_median_db": float(p50),
            "path_gain_p95_db": float(p95)}


def e4_baghdad_block(out: Path) -> dict:
    """Real OSM geometry: what each propagation mechanism adds, per band."""
    from bns.propagation.sionna_engine import Propagation, open_scene, path_gain_map
    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt

    scene_dir, tx, grid, outdoor, site = _block_setup()
    scene_meta = json.loads((scene_dir / "scene_meta.json").read_text(encoding="utf-8"))
    full_meta = json.loads((SCENES / "poc_full" / "scene_meta.json").read_text(encoding="utf-8"))
    baseline = Propagation(**FULL_SETTINGS)

    ladder_settings = [
        ("line of sight only", Propagation(max_depth=0, specular_reflection=False)),
        ("+ 1 reflection", Propagation(max_depth=1)),
        ("+ 2 reflections", Propagation(max_depth=2)),
        ("+ 2 reflections + diffraction (baseline)", baseline),
        ("3 reflections + diffraction", Propagation(max_depth=3, diffraction=True)),
        ("5 reflections + diffraction", Propagation(max_depth=5, diffraction=True)),
    ]
    scene = open_scene(scene_dir / "scene.xml", 3.5e9)
    ladder = []
    for label, settings in ladder_settings:
        res = path_gain_map(scene, tx, grid, settings, BLOCK_SAMPLES, [1])
        ladder.append({"mechanisms": label, **_outdoor_stats(res.mean, outdoor),
                       "seconds": round(res.seconds_per_seed[0], 2)})

    two = path_gain_map(scene, tx, grid, Propagation(max_depth=2), 10**7, [1, 2], keep_per_seed=True)
    a, b = two.per_seed
    both = (a > 0) & (b > 0)
    reflection_seed_rel_diff = float(np.max(np.abs(a[both] - b[both]) / a[both]))

    bands, maps = [], {}
    for sc in scenarios():
        scene_f = open_scene(scene_dir / "scene.xml", sc["frequency_hz"])
        res = path_gain_map(scene_f, tx, grid, baseline, BLOCK_SAMPLES, [1])
        bands.append({"scenario": sc["id"], "frequency_hz": sc["frequency_hz"],
                      **_outdoor_stats(res.mean, outdoor),
                      "seconds": round(res.seconds_per_seed[0], 2)})
        maps[sc["id"]] = res.mean
    np.savez_compressed(out / "path_gain_block.npz", x=grid.x_centers, y=grid.y_centers,
                        outdoor=outdoor, **maps)

    # Scene-size check. Buildings outside the block cannot block any path inside
    # it, so the diffracted power in the block must not drop when the scene is
    # enlarged from the 700 m crop to the full 1.3 km box. It does drop with
    # Sionna's default wedge table (wedges are lost to hash collisions), which
    # is why this project enlarges the table. Both settings are measured here.
    from bns.propagation import sionna_engine as engine

    diffraction_only = Propagation(max_depth=1, los=False, specular_reflection=False, diffraction=True)
    seeds = list(range(1, 9))

    def scene_size_check(slots: int) -> dict:
        engine.set_wedge_table_slots(slots)
        crop = path_gain_map(open_scene(scene_dir / "scene.xml", 3.5e9), tx, grid,
                             diffraction_only, BLOCK_SAMPLES, seeds)
        full = path_gain_map(open_scene(SCENES / "poc_full" / "scene.xml", 3.5e9), tx, grid,
                             diffraction_only, BLOCK_SAMPLES, seeds)
        lit = outdoor & (crop.mean > 0)
        ratio_db = linear_to_db(np.maximum(full.mean[lit], 1e-300) / crop.mean[lit])
        return {
            "wedge_table_slots": slots,
            "cells_compared": int(lit.sum()),
            "block_diffracted_power_crop": float(crop.mean[outdoor].sum()),
            "block_diffracted_power_full": float(full.mean[outdoor].sum()),
            "total_power_ratio_db": float(linear_to_db(full.mean[lit].sum() / crop.mean[lit].sum())),
            "median_ratio_db": float(np.median(ratio_db)),
            "fraction_losing_more_than_3_db": float(np.mean(ratio_db < -3.0)),
            "median_relative_noise_8_seeds": float(np.median(crop.std_error[lit] / crop.mean[lit])),
            "seconds_per_seed": round(float(np.mean(full.seconds_per_seed[1:])), 2),
        }

    default_table = scene_size_check(engine.SIONNA_DEFAULT_WEDGE_SLOTS)
    enlarged_table = scene_size_check(engine.WEDGE_TABLE_SLOTS)
    crop_check = {
        "wedges_in_crop_scene": scene_meta["mesh"]["wedges"],
        "wedges_in_full_scene": full_meta["mesh"]["wedges"],
        "sionna_default_table": default_table,
        "enlarged_table_used_by_project": enlarged_table,
        "power_recovered_in_full_scene_db": float(linear_to_db(
            enlarged_table["block_diffracted_power_full"] / default_table["block_diffracted_power_full"])),
    }
    crop_ok = bool(abs(enlarged_table["total_power_ratio_db"]) < 0.5
                   and abs(enlarged_table["median_ratio_db"]) < 0.5)

    style.apply()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    half = grid.cell_size_m / 2
    extent = [grid.x_centers[0] - half, grid.x_centers[-1] + half,
              grid.y_centers[0] - half, grid.y_centers[-1] + half]
    colours = style.SEQUENTIAL.copy()
    colours.set_under(style.SURFACE)
    for ax, sid, title in ((axes[0], "nr_3500", "3.5 GHz"), (axes[1], "nr_28000", "28 GHz")):
        shown = linear_to_db(np.where(maps[sid] > 0, maps[sid], 1e-300))
        shown = np.where(outdoor, shown, np.nan)
        im = ax.imshow(shown, origin="lower", extent=extent, cmap=colours, vmin=-150, vmax=-70)
        ax.plot(tx[0], tx[1], marker="^", color=style.INK, markersize=7, linestyle="none")
        ax.set(title=f"Path gain at {title}", xlabel="x [m]")
        ax.grid(False)
    axes[0].set_ylabel("y [m]")
    fig.colorbar(im, ax=axes, label="path gain [dB]", shrink=0.85, extend="min")
    fig.text(0.125, 0.01, "Triangle: rooftop site. Grey: buildings. Background colour: no path found. "
             "Building heights are mostly placeholders, so this shows the method, not Baghdad's coverage.",
             fontsize=8, color=style.INK_SECONDARY)
    fig.savefig(out / "e4_baghdad_block.png")
    plt.close(fig)

    return {"experiment": "E4 Baghdad block", "passed": crop_ok,
            "checks": {"diffraction_unaffected_by_scene_size": crop_ok},
            "warning": ("Most building heights are placeholders (see height_sources). These numbers "
                        "show that the engine and pipeline work; they are not findings about Baghdad."),
            "scene": {"buildings": scene_meta["buildings"],
                      "height_sources": scene_meta["height_sources"],
                      "mesh": scene_meta["mesh"]},
            "site": site, "grid": {"size_m": grid.size_xy, "cell_m": grid.cell_size_m},
            "samples": BLOCK_SAMPLES, "ladder_3p5ghz": ladder,
            "reflection_seed_max_relative_difference": reflection_seed_rel_diff,
            "bands_baseline": bands, "scene_size_check": crop_check}


def e5_convergence(out: Path) -> dict:
    """How many rays a map needs, for 5 m and 10 m cells, on the Baghdad block."""
    from bns.propagation.sionna_engine import Propagation, open_scene, path_gain_map
    from bns.reporting import plotstyle as style
    import matplotlib.pyplot as plt

    scene_dir, tx, grid, outdoor, site = _block_setup()
    scene = open_scene(scene_dir / "scene.xml", 3.5e9)
    baseline = Propagation(**FULL_SETTINGS)

    def coarse(a):      # 2x2 block mean: 5 m cells -> 10 m cells
        return a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean(axis=(1, 3))

    outdoor_10 = coarse(outdoor.astype(float)) == 1.0
    reference_n = 10**9
    reference = path_gain_map(scene, tx, grid, baseline, reference_n, [1])
    reference_seconds = reference.seconds_per_seed[0]

    def compare(test, ref, mask):
        t, r = test[mask], ref[mask]
        reached = r > 0
        both = reached & (t > 0)
        diff = linear_to_db(t[both] / r[both])
        return {"missed_fraction": float(np.mean(reached & (t <= 0)) / max(reached.mean(), 1e-12)),
                "median_abs_db": float(np.median(np.abs(diff))),
                "p95_abs_db": float(np.percentile(np.abs(diff), 95)),
                "rms_db": float(np.sqrt(np.mean(diff**2))),
                "max_abs_db": float(np.abs(diff).max())}

    rows = []
    for n in (10**6, 10**7, 10**8):
        res = path_gain_map(scene, tx, grid, baseline, n, [1])
        rows.append({"samples": n, "seconds": round(res.seconds_per_seed[0], 2),
                     "cells_5m": compare(res.mean, reference.mean, outdoor),
                     "cells_10m": compare(coarse(res.mean), coarse(reference.mean), outdoor_10)})

    # A second 1e9 run with another seed isolates the noise of the random parts
    # (diffraction) at the reference ray count: the floor nothing can go below.
    repeat = path_gain_map(scene, tx, grid, baseline, reference_n, [2])
    floor = {"cells_5m": compare(repeat.mean, reference.mean, outdoor),
             "cells_10m": compare(coarse(repeat.mean), coarse(reference.mean), outdoor_10)}

    style.apply()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ns = [r["samples"] for r in rows]
    for key, label, colour in (("cells_5m", "5 m cells", style.SCENARIO_COLORS["lte_1800"]),
                               ("cells_10m", "10 m cells", style.SCENARIO_COLORS["nr_3500"])):
        ys = [r[key]["p95_abs_db"] for r in rows]
        ax.loglog(ns, ys, marker="o", color=colour, label=label)
        style.label_line_end(ax, ns[-1], ys[-1], label)
    ax.set(title="Difference from a 1-billion-ray map, Baghdad block, 3.5 GHz",
           xlabel="rays per site", ylabel="95 % of cells differ by less than [dB]")
    ax.set_xlim(right=ns[-1] * 4)
    ax.set_yticks([1, 2, 5, 10, 20, 30], labels=["1", "2", "5", "10", "20", "30"])
    ax.minorticks_off()
    ax.legend(loc="lower left")
    fig.savefig(out / "e5_convergence.png")
    plt.close(fig)

    return {"experiment": "E5 convergence", "passed": True,
            "note": ("Informative: it sets the ray count per grid spacing. Rays start on a fixed "
                     "lattice, so line-of-sight and reflected power do not change with the seed."),
            "site": site, "settings": FULL_SETTINGS, "reference_samples": reference_n,
            "reference_seconds": round(reference_seconds, 1), "rows": rows,
            "seed_to_seed_at_reference": floor}


EXPERIMENTS = {"e1": e1_free_space, "e2": e2_ground_reflection, "e3": e3_diffraction,
               "e4": e4_baghdad_block, "e5": e5_convergence}


def worker(name: str, out: Path) -> None:
    info = runtime.init()
    start = time.perf_counter()
    result = EXPERIMENTS[name](out)
    result.update({"tolerances": TOL, "runtime": info, "versions": runtime.versions(),
                   "wall_seconds": round(time.perf_counter() - start, 1)})
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiments", nargs="+", choices=[*EXPERIMENTS, "all"])
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        worker(args.experiments[0], args.out)
        return 0

    names = list(EXPERIMENTS) if "all" in args.experiments else args.experiments
    all_passed = True
    for name in names:
        final = OUT / name
        staging = OUT / f"{name}.staging"
        attempts = runtime.run_isolated(
            [sys.executable, str(Path(__file__).resolve()), name, "--worker", "--out", str(staging)],
            staging, final)
        (final / "attempts.json").write_text(json.dumps(attempts, indent=2), encoding="utf-8")
        result = json.loads((final / "result.json").read_text(encoding="utf-8"))
        all_passed &= result["passed"]
        print(f"{result['experiment']}: {'PASS' if result['passed'] else 'FAIL'} "
              f"({result['wall_seconds']} s, {len(attempts)} attempt(s)) -> {final}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
