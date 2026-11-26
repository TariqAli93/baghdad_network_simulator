"""The research baseline: a fingerprint of the approved scientific configuration (provenance).

`configs/research_baseline.yaml` holds a fingerprint (SHA-256 of the canonical JSON) of every
value of the approved configuration. `check` compares the configuration files with it:

    baseline      unchanged: the value is the approved research baseline
    modified      the file now holds another value: runs with it are custom experiments
    not recorded  a new configuration item that is not part of the recorded baseline

Nothing here asks for an approval or blocks a run: a configuration that differs from the
baseline is simply classified and recorded as a custom experiment. Only scientific content is fingerprinted (values, units, definitions, constants);
comments and wording can be edited freely. A deliberate update of the baseline (e.g. a
documented candidate-threshold refinement) is recorded with
`scripts/research_baseline.py --record` and described in docs/approval-record.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

FILE = Path("configs") / "research_baseline.yaml"
_RADIO_FIELDS = ("value", "unit", "definition")
_SKIP = ("status", "approved_by")


@dataclass(frozen=True)
class Item:
    name: str
    state: str            # baseline | modified | not recorded
    fingerprint: str
    recorded: str | None


def _yaml(root: Path, name: str) -> dict:
    path = Path(root) / "configs" / name
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def fingerprint(value) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def items(root: Path) -> dict[str, object]:
    """Name -> scientific content of every configuration item that belongs to the baseline."""
    out: dict[str, object] = {}
    radio = _yaml(root, "radio_system.yaml")
    for name, e in (radio.get("parameters") or {}).items():
        out[f"radio.{name}"] = {k: e.get(k) for k in _RADIO_FIELDS}
    mappings = {k: {c: v for c, v in m.items() if c in ("alpha", "sinr_min_db", "sinr_max_db",
                                                        "thr_max_bps_hz", "based_on")}
                for k, m in (radio.get("rate_mappings") or {}).items()}
    out["rate_mappings"] = {"mappings": mappings, "assignment": radio.get("scenario_rate_mapping")}
    rule = _yaml(root, "site_rule.yaml")
    out["site_rule"] = {k: v for k, v in rule.items() if k not in _SKIP}
    study = _yaml(root, "study_area.yaml")
    for name, a in (study.get("areas") or {}).items():
        if a.get("approved"):
            obs = a.get("observations") or {}
            out[f"area.{name}"] = {"center": a.get("center"), "receiver_area_m": a.get("receiver_area_m"),
                                   "margin_m": a.get("margin_m"), "snapshot": a.get("snapshot"),
                                   "footprint_sources": a.get("footprint_sources"),
                                   "observations": {k: obs.get(k) for k in ("worklist", "required_priorities",
                                                                            "method_requirements")}}
    out["height_policy"] = {k: v for k, v in (study.get("height_policy") or {}).items() if k not in _SKIP}
    sim = _yaml(root, "simulation.yaml")
    for name, p in (sim.get("profiles") or {}).items():
        if (p or {}).get("status") == "approved":
            out[f"profile.{name}"] = {"cell_size_m": p.get("cell_size_m"), "rays_per_site": p.get("rays_per_site")}
    out["research_backend"] = {"backend": sim.get("research_backend"),
                               "production": sorted(k for k, v in (sim.get("backends") or {}).items()
                                                    if (v or {}).get("status") == "production")}
    atmosphere = _yaml(root, "atmosphere.yaml")
    out["atmosphere_baseline"] = atmosphere.get("baseline")
    b1 = ((_yaml(root, "approvals.yaml").get("decisions") or {}).get("B1_validation") or {})
    out["B1_tolerance"] = {"los_median_abs_tolerance_db": b1.get("los_median_abs_tolerance_db")}
    return out


def check(root: Path) -> list[Item]:
    recorded = (_yaml(root, "research_baseline.yaml").get("items") or {})
    result = []
    for name, content in items(root).items():
        fp = fingerprint(content)
        old = recorded.get(name)
        state = "baseline" if old == fp else ("not recorded" if old is None else "modified")
        result.append(Item(name, state, fp, old))
    return result


def modified(root: Path) -> list[Item]:
    return [i for i in check(root) if i.state != "baseline"]


def record(root: Path, *, note: str, recorded_on: str) -> Path:
    """Record the current configuration as the research baseline (a deliberate, documented update)."""
    fingerprints = {name: fingerprint(content) for name, content in items(root).items()}
    path = Path(root) / FILE
    header = ("# Research baseline: fingerprints of the approved scientific configuration\n"
              "# (bns.analysis.research_baseline). Provenance only: written by scripts/research_baseline.py --record\n"
              "# when the baseline is deliberately updated. A configuration that differs from it runs as a\n"
              "# custom experiment.\n")
    body = yaml.safe_dump({"note": note, "recorded_on": recorded_on, "items": fingerprints},
                          sort_keys=False, allow_unicode=True)
    path.write_text(header + body, encoding="utf-8")
    return path
