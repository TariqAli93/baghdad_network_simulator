"""The research-baseline configuration as display rows, read from the configuration files (no UI code).

The application shows these tables instead of repeating any value: the configuration files are
the single source of truth. Each row says whether the file holds the research-baseline value
or a modified one (bns.analysis.research_baseline); approval provenance stays in
configs/approvals.yaml and docs/approval-record.md, not in the interface.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from bns.analysis import rate_models, research_baseline


def _yaml(root: Path, name: str) -> dict:
    return yaml.safe_load((Path(root) / "configs" / name).read_text(encoding="utf-8")) or {}


def _states(root: Path) -> dict[str, str]:
    return {i.name: i.state for i in research_baseline.check(root)}


def baseline_state(state: str | None) -> str:
    return "research baseline" if state == "baseline" else "modified (custom)"


def radio_rows(root: Path) -> list[dict]:
    states = _states(root)
    return [{"parameter": name, "value": e.get("value"), "unit": e.get("unit", ""), "definition": e.get("definition", ""),
             "configuration": baseline_state(states.get(f"radio.{name}")), "sources": ", ".join(e.get("sources") or [])}
            for name, e in (_yaml(root, "radio_system.yaml").get("parameters") or {}).items()]


def rate_rows(root: Path, scenarios: list[dict]) -> list[dict]:
    models = rate_models.load(Path(root) / "configs" / "radio_system.yaml")

    def row(sc):
        m = models.get(sc["id"])
        if m is None:
            return {"scenario": sc["label"], "practical mapping (beside Shannon)": "—", "α": None,
                    "lower bound [dB]": None, "cap": "—", "label": "", "sources": ""}
        return {"scenario": sc["label"], "practical mapping (beside Shannon)": m.label, "α": m.alpha,
                "lower bound [dB]": m.sinr_min_db,
                "cap": f"{m.thr_max_bps_hz:g} bit/s/Hz" if m.thr_max_bps_hz is not None else f"{m.sinr_max_db:g} dB",
                "label": "research approximation" if m.caveat else "3GPP mapping", "sources": ", ".join(m.sources)}
    return [{"scenario": "all five", "practical mapping (beside Shannon)": "Shannon bound B·log2(1+SINR) (upper bound)",
             "α": 1.0, "lower bound [dB]": None, "cap": "none", "label": "theoretical upper bound",
             "sources": "project description"}] + [row(sc) for sc in scenarios]


def site_rule_rows(root: Path) -> list[dict]:
    from bns.simulation.setup import bearing_to_scene_azimuth_rad

    rule, radio = _yaml(root, "site_rule.yaml"), _yaml(root, "radio_system.yaml").get("parameters") or {}
    states = _states(root)
    rule_state = baseline_state(states.get("site_rule"))

    def param(name):
        e = radio.get(name) or {}
        return e.get("value"), baseline_state(states.get(f"radio.{name}"))

    mast, mast_state = param("antenna_height_above_roof_m")
    sectors, sec_state = param("sectors_per_site")
    tilt, tilt_state = param("mechanical_downtilt_deg")
    bearings = [360.0 * k / int(sectors) for k in range(int(sectors))] if sectors else []
    yaws = [np.degrees(bearing_to_scene_azimuth_rad(b)) % 360 for b in bearings]
    t = rule.get("candidate_thresholds") or {}
    rows = [("Mast height above the roof", f"{mast} m", mast_state, "radio_system.yaml"),
            ("Sector bearings", f"{sectors} sectors at compass {', '.join(f'{b:g}' for b in bearings)}° "
             f"(0 = north, clockwise; ray-tracer yaw {', '.join(f'{y:g}' for y in yaws)}°)", sec_state,
             "radio_system.yaml"),
            ("Downtilt", f"{tilt}°", tilt_state, "radio_system.yaml"),
            ("Antenna position", f"{rule.get('antenna_position')} (facing each sector)", rule_state, "site_rule.yaml"),
            ("Inset from the roof edge", f"{rule.get('edge_inset_m')} m", rule_state, "site_rule.yaml"),
            ("Candidate roofs: height categories", ", ".join(rule.get("candidate_height_categories") or []), rule_state,
             "site_rule.yaml"),
            ("Minimum roof height", f"{t.get('min_roof_height_m')} m", rule_state, "site_rule.yaml"),
            ("Minimum roof area", f"{t.get('min_roof_area_m2')} m²", rule_state, "site_rule.yaml"),
            ("Minimum spacing", f"{t.get('min_spacing_m')} m", rule_state, "site_rule.yaml"),
            ("Candidate count target", "–".join(str(v) for v in rule.get("candidate_count_target") or []), rule_state,
             "site_rule.yaml"),
            ("Threshold refinements", "; ".join(str(a) for a in t.get("adjustments") or []) or "none", rule_state,
             "site_rule.yaml"),
            ("Never candidates (kept as obstacles)", ", ".join(rule.get("excluded_structures") or []), rule_state,
             "site_rule.yaml"),
            ("Site selection", rule.get("site_selection", ""), rule_state, "site_rule.yaml")]
    return [{"item": a, "value": str(b), "configuration": c, "file": d} for a, b, c, d in rows]


def study_area_rows(root: Path, area_name: str) -> list[dict]:
    data = _yaml(root, "study_area.yaml")
    a = (data.get("areas") or {})[area_name]
    policy = data.get("height_policy") or {}
    states = _states(root)
    area_state = baseline_state(states.get(f"area.{area_name}"))
    policy_state = baseline_state(states.get("height_policy"))
    c, size = a.get("center") or {}, a.get("receiver_area_m") or []
    obs = a.get("observations") or {}
    methods = "; ".join(f"{p}: {' or '.join(m).replace('_', ' ')}" for p, m in (obs.get("method_requirements") or {}).items())
    rows = [("Centre", f"{c.get('lat')} N, {c.get('lon')} E", area_state),
            ("Receiver area", " × ".join(f"{float(v):g}" for v in size) + " m", area_state),
            ("Building margin", f"{a.get('margin_m')} m", area_state),
            ("OSM snapshot", a.get("snapshot", ""), area_state),
            ("Footprint sources", ", ".join(a.get("footprint_sources") or ["osm"]) + " (footprints only)", area_state),
            ("Height priority", " > ".join(policy.get("priority") or []), policy_state),
            ("Storey height", f"{policy.get('storey_height_m')} m", policy_state),
            ("External height dataset", str(policy.get("external_height_dataset", "—")), policy_state),
            ("Height sensitivity analysis", str(policy.get("height_sensitivity", "—")), policy_state),
            ("Required observations", ", ".join(obs.get("required_priorities") or []) +
             (f" ({obs.get('stage')} stage)" if obs.get("stage") else ""), area_state),
            ("Accepted observation methods", methods or "any", area_state),
            ("Covered by sensitivity instead", ", ".join(obs.get("covered_by_sensitivity") or []) or "—", area_state)]
    return [{"item": x, "value": str(y), "configuration": z} for x, y, z in rows]


def backend_profile_rows(root: Path) -> list[dict]:
    sim = _yaml(root, "simulation.yaml")
    rows = []
    for name, p in (sim.get("profiles") or {}).items():
        rays = p.get("rays_per_site")
        use = ("research baseline" if p.get("status") == "approved" else
               "disabled" if rays is None else "development and preview")
        rows.append({"item": f"profile {name}", "value": f"{p.get('cell_size_m')} m cells, "
                     + ("not converged" if rays is None else f"{float(rays):.0e} rays per sector"),
                     "use": use, "final-scene convergence": p.get("final_scene_convergence", "—")})
    for name, b in (sim.get("backends") or {}).items():
        rows.append({"item": f"backend {name}", "value": (b or {}).get("status", ""),
                     "use": "research baseline and all runs" if name == sim.get("research_backend")
                     else "custom and development runs (numerical limits: docs/validation.md §7)",
                     "final-scene convergence": "—"})
    rows.append({"item": "backend auto", "value": "GPU if available, else CPU", "use": "custom and development runs",
                 "final-scene convergence": "—"})
    return rows
