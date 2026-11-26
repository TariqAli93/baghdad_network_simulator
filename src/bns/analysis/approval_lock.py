"""Approval lock: an approved scientific value that changes loses its approval until reconfirmed.

`configs/approval_lock.yaml` holds a fingerprint (SHA-256 of the canonical JSON) of every
approved scientific value at the time it was confirmed. `check` compares the current
configuration with it:

    locked        unchanged since it was confirmed
    changed       the value differs from the confirmed one: no longer approved
    not recorded  marked approved in a configuration file but never confirmed through the lock

Research runs refuse anything that is not "locked" (`require_unchanged`). Only scientific
content is fingerprinted (values, units, definitions, constants); comments, justifications and
`approved_by` wording can be edited freely. After the supervisor (re)confirms a value, the
lock is renewed with `scripts/approval_lock.py --record` and the record in
docs/approval-record.md is updated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

LOCK = Path("configs") / "approval_lock.yaml"
_RADIO_FIELDS = ("value", "unit", "definition")
_RULE_SKIP = ("status", "approved_by")


class ApprovalChanged(RuntimeError):
    """An approved value was changed (or never confirmed) and needs the supervisor's reconfirmation."""


@dataclass(frozen=True)
class Item:
    name: str
    state: str            # locked | changed | not recorded
    fingerprint: str
    recorded: str | None


def _yaml(root: Path, name: str) -> dict:
    path = Path(root) / "configs" / name
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def fingerprint(value) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def approved_items(root: Path) -> dict[str, object]:
    """Name -> the scientific content of every value currently marked approved."""
    items: dict[str, object] = {}
    radio = _yaml(root, "radio_system.yaml")
    for name, e in (radio.get("parameters") or {}).items():
        if e.get("status") == "approved":
            items[f"radio.{name}"] = {k: e.get(k) for k in _RADIO_FIELDS}
    if radio.get("rate_mapping_status") == "approved":
        mappings = {k: {c: v for c, v in m.items() if c in ("alpha", "sinr_min_db", "sinr_max_db",
                                                            "thr_max_bps_hz", "based_on")}
                    for k, m in (radio.get("rate_mappings") or {}).items()}
        items["rate_mappings"] = {"mappings": mappings, "assignment": radio.get("scenario_rate_mapping")}
    rule = _yaml(root, "site_rule.yaml")
    if rule.get("status") == "approved":
        items["site_rule"] = {k: v for k, v in rule.items() if k not in _RULE_SKIP + ("candidate_thresholds",)}
        thresholds = rule.get("candidate_thresholds") or {}
        if thresholds.get("status") == "approved":
            items["site_rule.candidate_thresholds"] = {k: v for k, v in thresholds.items() if k != "status"}
    study = _yaml(root, "study_area.yaml")
    for name, a in (study.get("areas") or {}).items():
        if a.get("approved"):
            obs = a.get("observations") or {}
            items[f"area.{name}"] = {"center": a.get("center"), "receiver_area_m": a.get("receiver_area_m"),
                                     "margin_m": a.get("margin_m"), "snapshot": a.get("snapshot"),
                                     "footprint_sources": a.get("footprint_sources"),
                                     "observations": {k: obs.get(k) for k in ("worklist", "required_priorities")}}
    policy = study.get("height_policy") or {}
    if policy.get("approved_by"):
        items["height_policy"] = {k: v for k, v in policy.items() if k != "approved_by"}
    sim = _yaml(root, "simulation.yaml")
    for name, p in (sim.get("profiles") or {}).items():
        if (p or {}).get("status") == "approved":
            items[f"profile.{name}"] = {"cell_size_m": p.get("cell_size_m"), "rays_per_site": p.get("rays_per_site")}
    if sim.get("research_backend"):
        items["research_backend"] = {"backend": sim["research_backend"],
                                     "production": sorted(k for k, v in (sim.get("backends") or {}).items()
                                                          if (v or {}).get("status") == "production")}
    b1 = ((_yaml(root, "approvals.yaml").get("decisions") or {}).get("B1_validation") or {})
    if b1.get("los_median_abs_tolerance_db") is not None:
        items["B1_tolerance"] = {"los_median_abs_tolerance_db": b1["los_median_abs_tolerance_db"]}
    return items


def check(root: Path) -> list[Item]:
    recorded = (_yaml(root, "approval_lock.yaml").get("items") or {})
    out = []
    for name, content in approved_items(root).items():
        fp = fingerprint(content)
        old = recorded.get(name)
        state = "locked" if old == fp else ("not recorded" if old is None else "changed")
        out.append(Item(name, state, fp, old))
    return out


def require_unchanged(root: Path) -> None:
    bad = [i for i in check(root) if i.state != "locked"]
    if bad:
        raise ApprovalChanged(
            "These approved values changed or were never confirmed, so they are not approved until the "
            "supervisor reconfirms them (scripts/approval_lock.py): "
            + ", ".join(f"{i.name} ({i.state})" for i in bad) + ".")


def record(root: Path, *, confirmed_by: str, confirmed_on: str) -> Path:
    """Write the lock for the current approved values (only after the supervisor confirmed them)."""
    items = {name: fingerprint(content) for name, content in approved_items(root).items()}
    path = Path(root) / LOCK
    header = ("# Approval lock: fingerprints of the approved scientific values (bns.analysis.approval_lock).\n"
              "# Generated by scripts/approval_lock.py --record after a (re)confirmation; do not edit by hand.\n"
              "# A value whose fingerprint differs is no longer approved and research runs refuse it.\n")
    body = yaml.safe_dump({"confirmed_by": confirmed_by, "confirmed_on": confirmed_on, "items": items},
                          sort_keys=False, allow_unicode=True)
    path.write_text(header + body, encoding="utf-8")
    return path
