"""Dataset quality report: how much of a building dataset rests on real information."""

from __future__ import annotations

from collections import Counter

import numpy as np

from bns.geospatial.heights import CATEGORIES, PLACEHOLDER, Building, has_conflict
from bns.geospatial.study_area import StudyArea


def _shares(weights: dict[str, float], keys) -> dict[str, float]:
    total = sum(weights.values())
    return {k: (100.0 * weights.get(k, 0.0) / total if total else 0.0) for k in keys}


def quality_report(buildings: list[Building], area: StudyArea, parse_report: dict,
                   clean_report: dict, mesh_report: dict, *, height_model: dict | None = None,
                   height_method_approved: bool = False, worklist: dict | None = None) -> dict:
    """Counts, shares and warnings for one built dataset, plus a fitness verdict.

    A dataset is fit for research only if the area is an approved study district, the
    height methodology is approved, and placeholder heights are acceptable: none at all, or,
    under the approved method (decision A2), only outside a COMPLETE observation worklist
    (`worklist`: {"listed", "observed", "unmatched"} from the observation file), their spread
    being reported by the height sensitivity analysis. Otherwise the reasons are listed.
    """
    count_by_category = Counter(b.height.category for b in buildings)
    area_by_category: Counter = Counter()
    count_by_source = Counter(b.height.source for b in buildings)
    area_by_source: Counter = Counter()
    for b in buildings:
        area_by_category[b.height.category] += b.polygon.area
        area_by_source[b.height.source] += b.polygon.area

    stats = {}
    for category in CATEGORIES:
        values = np.array([b.height.height_m for b in buildings if b.height.category == category])
        if values.size:
            stats[category] = {"min_m": float(values.min()), "median_m": float(np.median(values)),
                               "max_m": float(values.max())}

    footprint = float(sum(b.polygon.area for b in buildings))
    receiver_box = area.receiver_box()
    built_in_receivers = float(sum(b.polygon.intersection(receiver_box).area for b in buildings))
    warnings = [{"building_id": b.building_id, "warning": w}
                for b in buildings for w in b.height.warnings]
    placeholder_share = _shares(dict(count_by_category), CATEGORIES)[PLACEHOLDER]

    reasons = []
    if area.role != "study district":
        reasons.append(f"the area is a {area.role}, not the study district")
    if not area.approved:
        reasons.append("the area has not been approved by the supervisor")
    if not height_method_approved:
        reasons.append("the building-height methodology has not been approved")
    notes = []
    complete = (worklist is not None and worklist.get("listed", 0) > 0
                and worklist.get("observed") == worklist.get("listed") and not worklist.get("unmatched"))
    if placeholder_share > 0:
        if height_method_approved and complete:
            notes.append(f"{placeholder_share:.1f} % of buildings keep placeholder heights outside the completed "
                         "observation worklist; report their spread with the height sensitivity analysis (A2)")
        else:
            reasons.append(f"{placeholder_share:.1f} % of buildings have placeholder heights")
            if worklist is not None and not complete:
                reasons.append(f"observation worklist incomplete: {worklist.get('observed', 0)} of "
                               f"{worklist.get('listed', 0)} buildings observed, "
                               f"{worklist.get('unmatched', 0)} rows matching no building"
                               + (f", {len(worklist['insufficient'])} observed with a method class their "
                                  "priority does not accept" if worklist.get("insufficient") else ""))

    return {
        "area": {"name": area.name, "role": area.role, "approved": area.approved},
        "buildings": len(buildings),
        "missing_height_buildings": count_by_category.get(PLACEHOLDER, 0),
        "conflicting_buildings": sum(has_conflict(b.height) for b in buildings),
        "buildings_with_alternative_sources": sum(bool(b.height.alternatives) for b in buildings),
        "height_categories": {
            "by_count": {c: count_by_category.get(c, 0) for c in CATEGORIES},
            "by_count_percent": _shares(dict(count_by_category), CATEGORIES),
            "by_area_percent": _shares(dict(area_by_category), CATEGORIES),
        },
        "height_sources": {
            "by_count": dict(count_by_source),
            "by_area_percent": _shares(dict(area_by_source), sorted(count_by_source)),
        },
        "height_statistics": stats,
        "height_model": height_model,
        "height_warnings": warnings,
        "footprint_area_m2": footprint,
        "built_share_of_receiver_area_percent": 100.0 * built_in_receivers / receiver_box.area,
        "parse": parse_report,
        "cleaning": clean_report,
        "mesh": mesh_report,
        "fit_for_research": not reasons,
        "not_fit_reasons": reasons,
        "fitness_notes": notes,
        "observation_worklist": worklist,
    }


def render_markdown(report: dict) -> str:
    """The report as a short page a supervisor can read."""
    area = report["area"]
    cats = report["height_categories"]
    verdict = ("Fit for research." if report["fit_for_research"]
               else "**NOT fit for research:** " + "; ".join(report["not_fit_reasons"]) + ".")
    lines = [
        f"# Dataset quality report: {area['name']}",
        "",
        f"Role: {area['role']}. Approved as study district: {'yes' if area['approved'] else 'no'}.",
        "",
        verdict,
        "",
        "## Where the building heights come from",
        "",
        "| Category | Buildings | Share of buildings | Share of footprint area |",
        "|---|---|---|---|",
    ]
    for category in CATEGORIES:
        lines.append(f"| {category} | {cats['by_count'][category]} | "
                     f"{cats['by_count_percent'][category]:.1f} % | "
                     f"{cats['by_area_percent'][category]:.1f} % |")
    lines += ["", "| Source | Buildings | Share of footprint area |", "|---|---|---|"]
    for source, count in sorted(report["height_sources"]["by_count"].items()):
        lines.append(f"| {source} | {count} | "
                     f"{report['height_sources']['by_area_percent'][source]:.1f} % |")
    if report["height_model"]:
        model = report["height_model"]
        lines += ["", f"Placeholder heights come from height model `{model['name']}` "
                      f"({model['kind']}, seed {model['seed']}; "
                      f"{'approved' if model['approved'] else 'not approved'})."]
    lines += ["", "## Height values", "", "| Category | Min | Median | Max |", "|---|---|---|---|"]
    for category, s in report["height_statistics"].items():
        lines.append(f"| {category} | {s['min_m']:.1f} m | {s['median_m']:.1f} m | {s['max_m']:.1f} m |")
    mesh = report["mesh"]
    lines += [
        "",
        "## Geometry",
        "",
        f"- Buildings: {report['buildings']}; without any height information: "
        f"{report['missing_height_buildings']}; with more than one height source: "
        f"{report['buildings_with_alternative_sources']}; where sources disagree: "
        f"{report['conflicting_buildings']}.",
        f"- Relations read: {report['parse'].get('relations_read', 0)}; with missing members: "
        f"{report['parse'].get('relations_with_missing_members', 0)}; duplicate footprint pairs: "
        f"{report['parse'].get('duplicate_pairs', 0)}.",
        f"- Built share of the receiver area: {report['built_share_of_receiver_area_percent']:.1f} %.",
        f"- Elements skipped while reading: {report['parse'].get('skipped') or 'none'}.",
        f"- Cleaning: {report['cleaning'] or 'no changes'}.",
    ]
    if mesh:
        lines.append(f"- Mesh: {mesh.get('triangles')} triangles, {mesh.get('wedges')} wedges, "
                     f"{mesh.get('non_manifold_edges')} non-manifold edges, "
                     f"{mesh.get('degenerate_triangles')} degenerate triangles.")
    lines += ["", f"## Height warnings ({len(report['height_warnings'])})", ""]
    lines += [f"- {w['building_id']}: {w['warning']}" for w in report["height_warnings"][:50]] or ["None."]
    return "\n".join(lines) + "\n"
