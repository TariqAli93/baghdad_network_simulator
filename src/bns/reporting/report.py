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

LIMITATION_KEYS = ("heights", "validated", "shannon", "greedy", "validation_scope", "candidate_6g")


def limitations(lang: str = "en") -> list[str]:
    """The scientific limitations every report carries, in the report language."""
    from bns.i18n import translate

    return [" ".join(translate(lang, f"limitations.general.{k}").split()) for k in LIMITATION_KEYS]


LIMITATIONS = limitations("en")

_CSS = """body{font-family:"Noto Sans Arabic","Segoe UI",Tahoma,Arial,sans-serif;color:#1b1b19;max-width:1000px;margin:24px auto;padding:0 16px;
font-size:14px;line-height:1.45}h1{font-size:22px}h2{font-size:18px;margin-top:28px;border-bottom:1px solid #ddd}
h3{font-size:15px}table{border-collapse:collapse;margin:8px 0;font-size:12px}td,th{border:1px solid #ccc;
padding:3px 6px;text-align:start;vertical-align:top}th{background:#f1f0ec}.label{border-inline-start:4px solid #c96a12;
background:#fff4e5;color:#6b3a06;padding:6px 10px;font-weight:600}img{max-width:100%;margin:8px 0}
code{background:#f1f0ec;padding:0 3px}@media print{h2{page-break-before:auto}img{page-break-inside:avoid}}
.label span{display:block;font-weight:400;font-size:12px;margin-top:2px}
code,.ltr{direction:ltr;unicode-bidi:isolate}.source{direction:ltr;text-align:left}
.note{font-size:12px;color:#5b5a55}"""


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


def _height_text(area: dict, lang: str = "en") -> str:
    """Where the run's building heights come from (real footprints in every case)."""
    from bns.i18n import translate

    model = area.get("height_model") or {}
    if model.get("kind") == "synthetic_urban":
        return translate(lang, "report.heights.synthetic", name=model.get("name"), seed=model.get("seed"),
                         pct=model.get("synthetic") or 0)
    if model:
        return translate(lang, "report.heights.model", name=model.get("name"), seed=model.get("seed"))
    return translate(lang, "report.heights.default")


def value_source(manifest: dict, name: str, lang: str = "en") -> str:
    """Where a parameter value of a run came from: the research baseline, a custom value, or not recorded."""
    from bns.i18n import translate

    if "overrides" not in manifest:
        return translate(lang, "report.not_recorded")
    custom = name in (manifest.get("overrides") or {})
    return translate(lang, "report.value_sources." + ("custom" if custom else "baseline"))


def _class_texts(lang: str, c) -> tuple[str, str, str]:
    """(headline, details, table value) of the run's classification in the report language."""
    from bns import i18n

    if lang == "en":            # the English report keeps the classification module's own wording
        return c.result, c.details, (f"{c.result} (configuration: {c.configuration}; dataset: {c.dataset}; "
                                     f"validation: {c.validation})")
    tr = i18n.translator(lang)
    head, details = i18n.classification_texts(tr, c)
    result, configuration, dataset, validation = i18n.classification_names(tr, c)
    return head, details, tr("report.rows.classification_value", result=result, configuration=configuration,
                             dataset=dataset, validation=validation)


def build_html(run_dir: Path, *, extra_markdown: dict[str, str] | None = None,
               invalid_reason: str | None = None, lang: str = "en") -> str:
    """The report in English (default) or Arabic (right-to-left). Saved notes and figures are the run's
    English records; in Arabic they stay left-to-right with a note saying so."""
    from bns.analysis.classification import from_manifest
    from bns.i18n import LANGUAGES, RTL, translate, translator

    lang = lang if lang in LANGUAGES else "en"
    tr = translator(lang)

    def T(key: str, **values) -> str:
        return translate(lang, key, **values)

    E = html.escape
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    c = from_manifest(manifest)
    label, detail, class_value = _class_texts(lang, c)
    run_id = manifest.get("run_id", run_dir.name)
    created = manifest.get("created_utc", "")
    direction = "rtl" if lang in RTL else "ltr"
    parts = [f"<!doctype html><html lang='{lang}' dir='{direction}'><head><meta charset='utf-8'>"
             f"<title>{E(T('report.title', run=run_id))}</title><style>{_CSS}</style></head><body>",
             (f"<div class='label' style='border-color:#b00020;background:#fde7ea;color:#7a0014'>"
              f"{E(T('report.invalid', reason=invalid_reason))}</div>" if invalid_reason else ""),
             f"<div class='label'>{E(label)}<span>{E(detail)}</span></div>",
             f"<h1>{E(T('report.heading'))}</h1><p><code>{E(run_id)}</code>"
             f" · {E(T('report.created', date=created if lang == 'en' or not created else tr.date(created)))}</p>"]
    area = manifest.get("area", {})
    profile = manifest.get("profile", {})
    R = "report.rows."

    def term(group: str, value: str) -> str:
        """A recorded category name in the report language; unknown values stay as recorded."""
        return T(f"common.{group}.{value}") if tr.has(f"common.{group}.{value}") else value

    if manifest.get("overrides"):
        deviations = ", ".join(f"{k} = {v}" for k, v in manifest["overrides"].items())
    else:
        deviations = T("report.none") if "overrides" in manifest else T("report.not_recorded")
    profile_value = (T(R + "profile_value", name=profile.get("name"), cell=profile.get("cell_size_m"),
                       rays=f"{profile.get('rays_per_site'):.0e}") if profile.get("rays_per_site") else str(profile))
    rows = [(T(R + "classification"), class_value),
            (T(R + "kind"), manifest.get("kind", "single_site")), (T(R + "mode"), manifest.get("mode", "")),
            (T(R + "deviations"), deviations),
            (T(R + "area"), f"{area.get('name')} / {area.get('variant')} ({term('area_role', area.get('role', ''))})"),
            (T(R + "osm"), str(area.get("osm_snapshot_sha256", ""))[:16] + "..."),
            (T(R + "scene"), str(area.get("scene_fingerprint", ""))[:16] + "..."),
            (T(R + "heights"), _height_text(area, lang)),
            (T(R + "categories"), ", ".join(f"{term('height_category', k)} {v:.1f}" for k, v in
                                            (area.get("height_categories_percent") or {}).items())),
            (T(R + "profile"), profile_value),
            (T(R + "backend"), json.dumps(manifest.get("backend") or {"name": "cpu"})),
            (T(R + "versions"), ", ".join(f"{k} {v}" for k, v in (manifest.get("versions") or {}).items()
                                          if k in ("sionna-rt", "mitsuba", "drjit", "python")))]
    parts.append(f"<h2>{E(T('report.configuration'))}</h2><table>"
                 + "".join(f"<tr><th>{E(k)}</th><td>{E(str(v))}</td></tr>" for k, v in rows) + "</table>")
    params = manifest.get("radio_parameters") or {}
    if params:
        C = "report.radio_columns."
        parts.append(f"<h2>{E(T('report.radio'))}</h2><table><tr><th>{E(T(C + 'parameter'))}</th>"
                     f"<th>{E(T(C + 'value'))}</th><th>{E(T(C + 'source'))}</th></tr>" + "".join(
                         f"<tr><td>{E(k)}</td><td>{E(str(v.get('value', v) if isinstance(v, dict) else v))}</td>"
                         f"<td>{E(value_source(manifest, k, lang))}</td></tr>"
                         for k, v in params.items()) + "</table>")
    notes = [(name, (run_dir / name).read_text(encoding="utf-8"))
             for name in ("summary.md", "sensitivity.md", "backend_agreement.md", "near_site_nr_28000.md")
             if (run_dir / name).exists()] + list((extra_markdown or {}).items())
    if notes and T("report.notes_english"):
        parts.append(f"<p class='note'>{E(T('report.notes_english'))}</p>")
    for title, md in notes:
        parts.append(f"<div class='source' lang='en' dir='ltr'><h2>{E(title)}</h2>"
                     + markdown_to_html(_strip_label_line(md)) + "</div>")
    pngs = sorted(run_dir.glob("*.png"))
    if pngs and "classification" not in manifest:
        parts.append(f"<p><i>{E(T('report.old_figures'))}</i></p>")
    if pngs and T("report.figures_english"):
        parts.append(f"<p class='note'>{E(T('report.figures_english'))}</p>")
    for png in pngs:
        data = base64.b64encode(png.read_bytes()).decode("ascii")
        parts.append(f"<h3 class='ltr'>{E(png.name)}</h3><img alt='{E(png.name)}' src='data:image/png;base64,{data}'>")
    parts.append(f"<h2>{E(T('report.limitations'))}</h2><ul>"
                 + "".join(f"<li>{E(text)}</li>" for text in limitations(lang)) + "</ul>")
    parts.append(f"<div class='label'>{E(label)}<span>{E(detail)}</span></div></body></html>")
    return "\n".join(parts)
