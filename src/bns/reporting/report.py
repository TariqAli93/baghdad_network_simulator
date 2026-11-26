"""Printable, self-contained HTML report of a saved run (open in a browser, print to PDF).

Uses only what the run folder holds (manifest, summary, Markdown notes, PNG figures) and
keeps its label and limitations. No template engine: a small Markdown subset (headings,
paragraphs, bullet lists, tables, bold, inline code) is converted here.
"""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

LIMITATIONS = [
    "Dataset: unless the classification says 'Complete data', most building heights are placeholders (field "
    "observations pending); results on such data are preliminary simulations.",
    "Only research-baseline runs on a dataset fit for research, after the final-scene convergence and the "
    "MATLAB comparison, are validated research results; everything else is preliminary or experimental.",
    "Shannon rates are theoretical upper bounds for one user with the whole carrier; not network capacity or "
    "user throughput. A 3GPP mapping, where present, is reported beside them (the run summary names it).",
    "Greedy site selection is a heuristic; it does not give a minimum site count.",
    "Validation so far: analytical checks and comparison with 3GPP TR 38.901 (model-to-model). MATLAB "
    "cross-check prepared but not executed; no field measurements.",
    "Candidate 6G bands (8 and 15 GHz) are research assumptions, not finalized commercial 6G specifications.",
]

_CSS = """body{font-family:Segoe UI,Arial,sans-serif;color:#1b1b19;max-width:1000px;margin:24px auto;padding:0 16px;
font-size:14px;line-height:1.45}h1{font-size:22px}h2{font-size:18px;margin-top:28px;border-bottom:1px solid #ddd}
h3{font-size:15px}table{border-collapse:collapse;margin:8px 0;font-size:12px}td,th{border:1px solid #ccc;
padding:3px 6px;text-align:left;vertical-align:top}th{background:#f1f0ec}.label{border-left:4px solid #c96a12;
background:#fff4e5;color:#6b3a06;padding:6px 10px;font-weight:600}img{max-width:100%;margin:8px 0}
code{background:#f1f0ec;padding:0 3px}@media print{h2{page-break-before:auto}img{page-break-inside:avoid}}
.label span{display:block;font-weight:400;font-size:12px;margin-top:2px}"""


def _strip_label_line(md: str) -> str:
    """Saved notes start with the run's label line; the report shows the classification instead."""
    from bns.analysis.classification import display_text

    lines = display_text(md).splitlines()
    markers = ("APPROVED", "Preliminary Simulation", "Research Baseline", "Custom Experiment",
               "Sensitivity Analysis", "Validated Research Results")
    if lines and lines[0].startswith("# ") and any(m in lines[0] for m in markers):
        lines = lines[1:]
    return "\n".join(lines)


def _inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t)
    return t


def markdown_to_html(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("#"):
            level = min(len(line) - len(line.lstrip("#")) + 1, 4)
            out.append(f"<h{level}>{_inline(line.lstrip('#').strip())}</h{level}>")
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, *body = rows
            out.append("<table><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</table>")
        elif line.lstrip().startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith(("- ", "* ")):
                items.append(lines[i].lstrip()[2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + "</ul>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|")):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out)


def value_source(manifest: dict, name: str) -> str:
    """Where a parameter value of a run came from: the research baseline, a custom value, or not recorded."""
    if "overrides" not in manifest:
        return "not recorded (run before 2026-11-27)"
    return "custom value" if name in (manifest.get("overrides") or {}) else "research baseline"


def build_html(run_dir: Path, *, extra_markdown: dict[str, str] | None = None,
               invalid_reason: str | None = None) -> str:
    run_dir = Path(run_dir)
    from bns.analysis.classification import from_manifest

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    c = from_manifest(manifest)
    label = c.result
    detail = c.details
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>Report {html.escape(manifest.get('run_id', run_dir.name))}"
             f"</title><style>{_CSS}</style></head><body>",
             (f"<div class='label' style='border-color:#b00020;background:#fde7ea;color:#7a0014'>INVALID FOR RESEARCH "
              f"INTERPRETATION: {html.escape(invalid_reason)}</div>" if invalid_reason else ""),
             f"<div class='label'>{html.escape(label)}<span>{html.escape(detail)}</span></div>",
             f"<h1>Baghdad Network Simulator — run report</h1><p><code>{html.escape(manifest.get('run_id', run_dir.name))}</code>"
             f" · created {html.escape(manifest.get('created_utc', ''))}</p>"]
    area = manifest.get("area", {})
    profile = manifest.get("profile", {})
    rows = [("Classification", f"{c.result} (configuration: {c.configuration}; dataset: {c.dataset}; "
                                f"validation: {c.validation})"),
            ("Kind", manifest.get("kind", "single_site")), ("Mode", manifest.get("mode", "")),
            ("Values differing from the research baseline",
             ", ".join(f"{k} = {v}" for k, v in manifest["overrides"].items()) if manifest.get("overrides")
             else ("none" if "overrides" in manifest else "not recorded (run before 2026-11-27)")),
            ("Study area", f"{area.get('name')} / {area.get('variant')} ({area.get('role', '')})"),
            ("OSM snapshot SHA-256", str(area.get("osm_snapshot_sha256", ""))[:16] + "..."),
            ("Scene fingerprint", str(area.get("scene_fingerprint", ""))[:16] + "..."),
            ("Height categories (% of buildings)", ", ".join(f"{k} {v:.1f}" for k, v in
                                                             (area.get("height_categories_percent") or {}).items())),
            ("Profile", f"{profile.get('name')} — {profile.get('cell_size_m')} m cells, {profile.get('rays_per_site'):.0e} rays"
             if profile.get("rays_per_site") else str(profile)),
            ("Backend", json.dumps(manifest.get("backend") or {"name": "cpu"})),
            ("Versions", ", ".join(f"{k} {v}" for k, v in (manifest.get("versions") or {}).items()
                                   if k in ("sionna-rt", "mitsuba", "drjit", "python")))]
    parts.append("<h2>Configuration and provenance</h2><table>"
                 + "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows) + "</table>")
    params = manifest.get("radio_parameters") or {}
    if params:
        parts.append("<h2>Radio parameters used</h2><table><tr><th>Parameter</th><th>Value</th>"
                     "<th>Value from</th></tr>" + "".join(
                         f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v.get('value', v) if isinstance(v, dict) else v))}</td>"
                         f"<td>{html.escape(value_source(manifest, k))}</td></tr>"
                         for k, v in params.items()) + "</table>")
    for name in ("summary.md", "sensitivity.md", "backend_agreement.md", "near_site_nr_28000.md"):
        path = run_dir / name
        if path.exists():
            parts.append(f"<h2>{html.escape(name)}</h2>" + markdown_to_html(_strip_label_line(
                path.read_text(encoding="utf-8"))))
    for title, md in (extra_markdown or {}).items():
        parts.append(f"<h2>{html.escape(title)}</h2>" + markdown_to_html(_strip_label_line(md)))
    if sorted(run_dir.glob("*.png")) and "classification" not in manifest:
        parts.append("<p><i>Figures saved before 2026-11-27 keep the title written at run time; that run-time label corresponds to the class Preliminary Simulation.</i></p>")
    for png in sorted(run_dir.glob("*.png")):
        data = base64.b64encode(png.read_bytes()).decode("ascii")
        parts.append(f"<h3>{html.escape(png.name)}</h3><img alt='{html.escape(png.name)}' src='data:image/png;base64,{data}'>")
    parts.append("<h2>Scientific limitations</h2><ul>" + "".join(f"<li>{html.escape(t)}</li>" for t in LIMITATIONS)
                 + "</ul>")
    parts.append(f"<div class='label'>{html.escape(label)}<span>{html.escape(detail)}</span></div></body></html>")
    return "\n".join(parts)
