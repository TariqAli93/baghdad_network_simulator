"""The approved configuration as display rows, read from the configuration files (no UI code).

The application shows these tables instead of repeating any value: the configuration files
stay the single source of truth, and each row carries its effective approval state, which is
"approved" only while the approval lock confirms the value is unchanged since it was approved.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from bns.analysis import approval_lock, rate_models


def _yaml(root: Path, name: str) -> dict:
    return yaml.safe_load((Path(root) / "configs" / name).read_text(encoding="utf-8")) or {}


def _lock(root: Path) -> dict[str, str]:
    return {i.name: i.state for i in approval_lock.check(root)}


def effective(status: str, lock_state: str | None) -> str:
    """The approval a value really has: an approved value that changed is no longer approved."""
    if status != "approved":
        return status
    return "approved" if lock_state == "locked" else f"approval void ({lock_state or 'not recorded'}): reconfirm"


def radio_rows(root: Path) -> list[dict]:
    lock = _lock(root)
    rows = []
    for name, e in (_yaml(root, "radio_system.yaml").get("parameters") or {}).items():
        rows.append({"parameter": name, "value": e.get("value"), "unit": e.get("unit", ""),
                     "definition": e.get("definition", ""),
                     "approval": effective(e.get("status", "undecided"), lock.get(f"radio.{name}")),
                     "approved by": e.get("approved_by", ""), "sources": ", ".join(e.get("sources") or [])})
    return rows


def rate_rows(root: Path, scenarios: list[dict]) -> list[dict]:
    path = Path(root) / "configs" / "radio_system.yaml"
    models = rate_models.load(path)
    status, by = rate_models.approval(path)
    state = effective(status, _lock(root).get("rate_mappings"))
    rows = [{"scenario": sc["label"], "practical mapping (beside Shannon)": models[sc["id"]].label if sc["id"] in models else "—",
             "α": models[sc["id"]].alpha if sc["id"] in models else None,
             "lower bound [dB]": models[sc["id"]].sinr_min_db if sc["id"] in models else None,
             "cap": (f"{models[sc['id']].thr_max_bps_hz:g} bit/s/Hz" if models[sc["id"]].thr_max_bps_hz is not None
                     else f"{models[sc['id']].sinr_max_db:g} dB") if sc["id"] in models else "—",
             "label": "research approximation" if sc["id"] in models and models[sc["id"]].caveat else "3GPP mapping",
             "sources": ", ".join(models[sc["id"]].sources) if sc["id"] in models else "",
             "approval": state} for sc in scenarios]
    return [{"scenario": "all five", "practical mapping (beside Shannon)": "Shannon bound B·log2(1+SINR) (upper bound)",
             "α": 1.0, "lower bound [dB]": None, "cap": "none", "label": "theoretical upper bound",
             "sources": "project description", "approval": "approved"}] + rows


def site_rule_rows(root: Path) -> list[dict]:
    rule, radio = _yaml(root, "site_rule.yaml"), _yaml(root, "radio_system.yaml").get("parameters") or {}
    lock = _lock(root)
    rule_state = effective(rule.get("status", "undecided"), lock.get("site_rule"))

    def param(name):
        e = radio.get(name) or {}
        return e.get("value"), effective(e.get("status", "undecided"), lock.get(f"radio.{name}"))

    mast, mast_state = param("antenna_height_above_roof_m")
    sectors, sec_state = param("sectors_per_site")
    tilt, tilt_state = param("mechanical_downtilt_deg")
    from bns.simulation.setup import scene_azimuth_to_bearing_deg
    yaws = [360 * k / int(sectors) for k in range(int(sectors))] if sectors else []
    azimuths = ", ".join(f"{y:g}" for y in yaws) or "—"
    bearings = ", ".join(f"{scene_azimuth_to_bearing_deg(np.radians(y)):g}" for y in yaws) or "—"
    t = rule.get("candidate_thresholds") or {}
    pending = ((_yaml(root, "approvals.yaml").get("pending_proposals") or {}).get("candidate_thresholds") or {})
    rows = [("Mast height above the roof", f"{mast} m", mast_state, "radio_system.yaml"),
            ("Sectors and azimuths", f"{sectors} sectors, yaw {azimuths}° counter-clockwise from east = compass "
             f"bearings {bearings}°", sec_state, "radio_system.yaml"),
            ("Proposed: compass bearings 0, 120, 240°", "awaiting confirmation; not applied (30° rotation of the set)",
             "pending", "approvals.yaml"),
            ("Downtilt", f"{tilt}°", tilt_state, "radio_system.yaml"),
            ("Antenna position", f"{rule.get('antenna_position')} (facing each sector)", rule_state, "site_rule.yaml"),
            ("Inset from the roof edge", f"{rule.get('edge_inset_m')} m", rule_state, "site_rule.yaml"),
            ("Candidate roofs: height categories", ", ".join(rule.get("candidate_height_categories") or []), rule_state,
             "site_rule.yaml"),
            ("Candidate count target", "–".join(str(v) for v in rule.get("candidate_count_target") or []), rule_state,
             "site_rule.yaml"),
            ("Never candidates (kept as obstacles)", ", ".join(rule.get("excluded_structures") or []), rule_state,
             "site_rule.yaml"),
            ("Site selection", rule.get("site_selection", ""), rule_state, "site_rule.yaml")]
    for key, title in (("min_roof_height_m", "Minimum roof height"), ("min_roof_area_m2", "Minimum roof area"),
                       ("min_spacing_m", "Minimum spacing")):
        proposed = (pending.get("proposal") or {}).get(key)
        rows.append((title, ("PENDING (not specified)" if t.get(key) is None else t.get(key))
                     + (f"; evaluation value {proposed:g}, not approved" if proposed is not None else ""),
                     t.get("status", "pending"), "site_rule.yaml"))
    return [{"item": a, "value": str(b), "approval": c, "file": d} for a, b, c, d in rows]


def study_area_rows(root: Path, area_name: str) -> list[dict]:
    data = _yaml(root, "study_area.yaml")
    a = (data.get("areas") or {})[area_name]
    policy = data.get("height_policy") or {}
    lock = _lock(root)
    area_state = effective("approved" if a.get("approved") else "not approved", lock.get(f"area.{area_name}"))
    policy_state = effective("approved" if policy.get("approved_by") else "not approved", lock.get("height_policy"))
    c, size = a.get("center") or {}, a.get("receiver_area_m") or []
    obs = a.get("observations") or {}
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
            ("Covered by sensitivity instead", ", ".join(obs.get("covered_by_sensitivity") or []) or "—", area_state)]
    if a.get("condition"):
        rows.append(("Condition", a["condition"], area_state))
    return [{"item": x, "value": str(y), "approval": z} for x, y, z in rows]


def backend_profile_rows(root: Path) -> list[dict]:
    sim, lock = _yaml(root, "simulation.yaml"), _lock(root)
    rows = []
    for name, p in (sim.get("profiles") or {}).items():
        rays = p.get("rays_per_site")
        rows.append({"item": f"profile {name}", "value": f"{p.get('cell_size_m')} m cells, "
                     + ("disabled" if rays is None else f"{float(rays):.0e} rays per sector"),
                     "status": effective(p.get("status", ""), lock.get(f"profile.{name}")),
                     "final-scene convergence": p.get("final_scene_convergence", "—")})
    for name, b in (sim.get("backends") or {}).items():
        rows.append({"item": f"backend {name}", "value": "research backend" if name == sim.get("research_backend")
                     else "development only", "status": (b or {}).get("status", ""), "final-scene convergence": "—"})
    rows.append({"item": "backend auto", "value": "development only (may pick the GPU)", "status": "development",
                 "final-scene convergence": "—"})
    return rows


def decisions(root: Path) -> list[dict]:
    d = _yaml(root, "approvals.yaml").get("decisions") or {}
    return [{"decision": k, "status": v.get("status", ""), "approved on": ", ".join(map(str, v["approved_on"]))
             if isinstance(v.get("approved_on"), list) else str(v.get("approved_on", "")),
             "open condition": " ".join(str(v.get("condition", "")).split()) or "—"} for k, v in d.items()]


def unspecified(root: Path) -> list[dict]:
    return list(_yaml(root, "approvals.yaml").get("unspecified") or [])


def approval_source(root: Path) -> str:
    """One sentence on where the approvals come from (configs/approvals.yaml, record)."""
    rec = _yaml(root, "approvals.yaml").get("record") or {}
    dates = ", ".join(str(r.get("reported_on")) for r in rec.get("reports") or [])
    return (f"Reported by the {rec.get('reported_by', 'project owner')} on {dates or 'unknown dates'}; "
            f"approval reference: {rec.get('approval_reference', 'none')}.")
