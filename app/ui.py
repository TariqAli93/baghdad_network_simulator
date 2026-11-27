"""Shared Streamlit helpers: language, labels, cached loaders and the map figure.

UI code only. Every number shown comes from saved runs, configuration files or
the bns package; nothing scientific is computed here. All user-facing text goes
through `t()` (bns.i18n): Arabic (default, right-to-left) or English.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml

from bns import i18n
from bns.app import preferences, results
from bns.reporting import plotstyle as style

ROOT = Path(__file__).resolve().parents[1]
SEQ = [[i / 6, c] for i, c in enumerate(["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])]
SITE_COLOURS = ["#2a6f97", "#c0504d", "#5b8c3a", "#8064a2", "#d08c2b", "#4b9b9b", "#7a6a53", "#b5527a"]
CATEGORY_COLOURS = {"observed": "#1b7f5b", "estimated": "#d08c2b", "synthetic": "#7b8fb5", "placeholder": "#b9b8b0"}
# name in the saved arrays -> (unit, colour range, kind); titles come from coverage.layers.<name>
LAYERS = {
    "path_gain_db": ("dB", (-160, -60), "seq"),
    "rx_power_dbm": ("dBm", (-120, -20), "seq"),
    "sinr_db": ("dB", (-10, 40), "seq"),
    "rate_bps": ("Mbit/s", None, "rate"),
    "rate_3gpp_bps": ("Mbit/s", None, "rate"),
    "covered": ("", (0, 1), "binary"),
    "serving_site": ("", None, "site"),
    "interference_dbm": ("dBm", (-130, -50), "seq"),
}


# ---------------------------------------------------------------- language
_LAST = {"lang": i18n.DEFAULT}


def lang() -> str:
    """The selected language: session state, else the ?lang= query parameter, else the language saved on
    this computer (bns.app.preferences: it survives a restart), else Arabic.

    Outside a script run (e.g. the test harness formatting widget options) there is no session;
    the language of the latest run is used then."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    if get_script_run_ctx() is None:
        return _LAST["lang"]
    if "lang" not in st.session_state:
        requested = st.query_params.get("lang")
        saved = preferences.load(preferences.location(ROOT)).get("lang")
        st.session_state["lang"] = requested if requested in i18n.LANGUAGES else \
            saved if saved in i18n.LANGUAGES else i18n.DEFAULT
    _LAST["lang"] = st.session_state["lang"]
    return _LAST["lang"]


def tr() -> i18n.Translator:
    return i18n.translator(lang())


def t(key: str, count=None, **values) -> str:
    return i18n.translate(lang(), key, count, **values)


def language_switch() -> None:
    """Arabic / English switch; the choice persists across reruns, pages, (via ?lang=) reloads and (via the
    saved preference) application restarts."""
    current = lang()

    def changed():
        if st.session_state["lang_switch"] in i18n.LANGUAGES:
            st.session_state["lang"] = st.session_state["lang_switch"]
            preferences.save(preferences.location(ROOT), lang=st.session_state["lang"])

    st.segmented_control(t("common.language"), list(i18n.LANGUAGES), default=current, key="lang_switch",
                         format_func=lambda code: i18n.translate(code, f"common.language_names.{code}"),
                         on_change=changed, label_visibility="collapsed")
    if st.query_params.get("lang") != lang():
        st.query_params["lang"] = lang()


def ltr(text) -> str:
    """Keep a technical fragment (numbers with units, identifiers, paths) left-to-right inside Arabic text."""
    return f'<span dir="ltr" class="ltr">{text}</span>'


def inject_css() -> None:
    """One style block in both languages (each block takes a row of page spacing, so the layout is the
    same in Arabic and English); the top padding keeps the language switch below Streamlit's header."""
    rtl = tr().rtl
    st.markdown("""
<style>
div.block-container, [data-testid="stMainBlockContainer"] {padding-top: 3.25rem;}
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
  font-family: "Noto Sans Arabic", "Segoe UI", Tahoma, "Source Sans Pro", sans-serif;}
.result-banner {border-inline-start: 4px solid #8a6d3b; background: rgba(201,106,18,.08); padding: .45rem .8rem;
                 border-radius: 4px; margin: .2rem 0 .8rem 0; display: flex; flex-wrap: wrap; gap: .2rem .9rem;
                 align-items: baseline;}
.result-banner span {font-size: .82rem; opacity: .85;}
.result-banner.experiment {border-color: #2a6f97; background: rgba(42,111,151,.08);}
.result-banner.validated {border-color: #1b7f5b; background: rgba(27,127,91,.10);}
.card {border: 1px solid rgba(128,128,128,.25); border-radius: 8px; padding: .8rem 1rem; height: 100%;}
.card .label {font-size: .8rem; opacity: .75;}
.card .value {font-size: 1.35rem; font-weight: 600; margin: .15rem 0;}
.card .sub {font-size: .8rem; opacity: .8;}
div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
section[data-testid="stSidebar"] .sidebar-note {font-size: .8rem; opacity: .75;}
.ltr, code, pre {direction: ltr; unicode-bidi: isolate;}
div.ltr {text-align: left;}
table.kv {border-collapse: collapse; width: 100%; font-size: .9rem; margin-bottom: .6rem;}
table.kv th, table.kv td {border: none; border-bottom: 1px solid rgba(128,128,128,.2); padding: .3rem .5rem;
                          text-align: start; vertical-align: top;}
table.kv th {font-weight: 600; width: 45%;}
""" + ("""
/* Arabic: text containers right-to-left; charts, tables, code, numbers and inputs stay left-to-right
   (Streamlit's native widgets and the sidebar position are not mirrored by the framework). The language
   switch keeps its own left-to-right drawing: its rounded outer corners are not mirrored either. */
[data-testid="stMainBlockContainer"], [data-testid="stSidebarContent"] {direction: rtl;}
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"], [data-testid="stHeading"],
[data-testid="stMetricLabel"], [data-testid="stWidgetLabel"], [data-testid="stExpander"] summary,
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentWarning"], [data-testid="stAlertContentError"],
[data-testid="stAlertContentSuccess"] {text-align: right;}
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"], [data-testid="stCode"], [data-testid="stMetricValue"],
input[type="number"], [data-testid="stImage"], .st-key-lang_switch {direction: ltr; unicode-bidi: isolate;}
""" if rtl else "") + "</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------- page elements
def page_header(title_key: str, caption_key: str | None = None) -> None:
    st.title(t(title_key))
    if caption_key:
        st.caption(t(caption_key))


def result_banner(classification) -> None:
    """The scientific classification of a result: what it is, its configuration, data and validation."""
    from bns.analysis import classification as cl

    if classification is None:
        return
    kind = "validated" if classification.validated else (
        "preliminary" if classification.result == cl.PRELIMINARY else "experiment")
    head, details = i18n.classification_texts(tr(), classification)
    st.markdown(f'<div class="result-banner {kind}"><b>{head}</b><span>{details}</span></div>',
                unsafe_allow_html=True)


def label_classification(text: str):
    """Classification of a saved note from its label line; labels written before 2026-11-27 describe
    runs whose configuration was not recorded, on incomplete data, before validation."""
    from bns.analysis import classification as cl

    parts = [p.strip() for p in text.split("·")]
    known = {cl.BASELINE, cl.CUSTOM, cl.SENSITIVITY, cl.NOT_RECORDED}
    config = next((p for p in parts if p in known), None)
    if config is None:
        return cl.Classification(cl.NOT_RECORDED, cl.INCOMPLETE, cl.PENDING)
    return cl.Classification(config, cl.COMPLETE if cl.COMPLETE in parts else cl.INCOMPLETE,
                             cl.VALIDATED if cl.VALIDATED in parts else cl.PENDING)


def limitation_texts(items: list[tuple[str, dict]]) -> list[str]:
    """Translated limitation sentences from bns.simulation.experiment.limitation_items."""
    out = []
    for key, values in items:
        values = dict(values)
        if "role" in values:
            values["role"] = t(f"common.area_role.{values['role']}")
        if key == "limitations.deviations":
            values["items"] = i18n.list_separator(tr()).join(i18n.deviation_text(tr(), d)
                                                             for d in values["items"].split("; "))
        out.append(t(key, **values))
    return out


def error_box(exc: Exception) -> None:
    """A translated error category, with the original diagnostic message kept in an expander."""
    message = str(exc)
    category = ("missing_dataset" if "No dataset" in message or "quality report" in message else
                "invalid_value" if "valid range" in message or "must be" in message else
                "no_gpu" if "GPU" in message or "NVIDIA" in message or "CUDA" in message else "unknown")
    st.error(t(f"common.error_category.{category}") + " " + t("common.error_hint"))
    with st.expander(t("common.technical_details")):
        st.code(message, language="text")


def card(label: str, value: str, sub: str = "", tooltip: str = "") -> None:
    """A metric card; `tooltip` explains an acronym or how the value is formed (shown on hover)."""
    import html as _html

    title = f' title="{_html.escape(tooltip, quote=True)}"' if tooltip else ""
    st.markdown(f'<div class="card"{title}><div class="label">{label}</div><div class="value">{value}</div>'
                f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- data access
@st.cache_data(show_spinner=False)
def scenarios() -> list[dict]:
    from bns.simulation.experiment import load_scenarios
    return load_scenarios(ROOT)


def colour(scenario_id: str) -> str:
    return style.SCENARIO_COLORS.get(scenario_id, style.INK_SECONDARY)


def scenario_name(sc: dict) -> str:
    """'5G — 3.5 GHz' in the selected language (scenario labels in the config stay English identifiers)."""
    key = f"common.band.{sc['id']}"
    return t(key) if tr().has(key) else band_name(sc["label"], sc["frequency_hz"] / 1e9)


def scenario_status(sc: dict) -> str:
    return t(f"common.scenario_status.{sc.get('status', '')}")


@st.cache_data(show_spinner=False)
def study_areas() -> dict:
    return yaml.safe_load((ROOT / "configs" / "study_area.yaml").read_text(encoding="utf-8"))["areas"]


def default_variant(area: str, variants: list[str]) -> int:
    """Index of the area's configured primary variant (configs/study_area.yaml), else 'osm', else the
    first; never chosen by alphabetical accident when a primary variant is configured."""
    primary = (study_areas().get(area) or {}).get("primary_variant")
    for name in (primary, "osm"):
        if name in variants:
            return variants.index(name)
    return 0


def variant_name(variant: str) -> str:
    """A readable name for a dataset variant; the identifier stays visible as technical detail."""
    base = variant.split("+")[0]
    key = f"study_area.variants.{base.split('-seed')[0]}"
    ident = f"{i18n.LRI}{variant}{i18n.PDI}" if tr().rtl else variant    # identifier stays left-to-right
    return f"{t(key)} ({ident})" if tr().has(key) else variant


def height_display_category(b) -> str:
    """observed / estimated / synthetic (Synthetic Urban Model or another height model) / placeholder."""
    if b.height.category == "placeholder" and b.height.source.startswith("model:"):
        return "synthetic"
    return b.height.category


def variants(area: str) -> list[str]:
    folder = ROOT / "data" / "scenes" / area
    return sorted(d.name for d in folder.iterdir() if (d / "scene.xml").exists()) if folder.exists() else []


@st.cache_resource(show_spinner=False)
def buildings(area: str, variant: str):
    """Footprints in local metres with their height records (from the scene's building table)."""
    from bns.geospatial import pipeline
    from bns.geospatial.study_area import load_study_areas

    a = load_study_areas(ROOT / "configs" / "study_area.yaml")[area]
    return a, pipeline.load_buildings(ROOT / "data" / "scenes" / area / variant, a)


def outline_xy(polygons) -> tuple[list, list]:
    xs, ys = [], []
    for poly in polygons:
        for ring in [poly.exterior, *poly.interiors]:
            x, y = ring.xy
            xs += list(x) + [None]
            ys += list(y) + [None]
    return xs, ys


@st.cache_data(show_spinner=False, ttl=30)
def run_list() -> list[str]:
    return [str(r.path) for r in results.list_runs(ROOT)]


@st.cache_resource(show_spinner=False, max_entries=6)
def run(path: str) -> results.Run:
    return results.load_run(Path(path))


def run_title(r: results.Run) -> str:
    m = r.manifest
    sites = t("common.candidates", count=len(r.sites)) if r.kind == "site_plan" else t("common.sites", count=len(r.sites))
    title = t("common.run_title", date=tr().date(m.get("created_utc", "")), sites=sites,
              profile=m["profile"]["name"], area=f"{m['area']['name']}/{m['area'].get('variant', '')}")
    return (t("common.invalid_prefix") + " · " if r.invalid else "") + title


def pick_run(key: str, *, kinds: tuple[str, ...] = ("single_site", "multi_site")) -> results.Run | None:
    paths = [p for p in run_list() if run(p).kind in kinds]
    if not paths:
        st.info(t("common.no_runs_kind"))
        return None
    chosen = st.selectbox(t("common.saved_run"), paths, format_func=lambda p: run_title(run(p)), key=key)
    if run(chosen).invalid:
        st.error(t("common.invalid_run", reason=recorded(run(chosen).invalid)))
    return run(chosen)


def recorded(text):
    """A status text recorded in English (stop reason, invalid-run reason) in the selected language when it
    is recognised; otherwise exactly as recorded (bns.i18n.recorded_text)."""
    return i18n.recorded_text(tr(), text)


def layer_title(layer: str) -> str:
    key = f"coverage.layers.{layer}"
    return t(key) if tr().has(key) else layer


def map_figure(grid, z, outdoor, *, layer: str, sites: list[dict], azimuths: list[float] | None = None,
               footprints=None, height: int = 620, zrange=None) -> go.Figure:
    unit, default_range, kind = LAYERS.get(layer, ("", None, "seq"))
    title = layer_title(layer)
    shown = np.where(outdoor, z.astype(float), np.nan)
    if kind == "rate":
        shown = shown / 1e6
        finite = shown[np.isfinite(shown) & (shown > 0)]
        default_range = (0, float(np.percentile(finite, 99))) if finite.size else (0, 1)
    shown = np.where(np.isfinite(shown), shown, np.nan if kind != "seq" else -1e9)
    shown = np.where(outdoor, shown, np.nan)
    fig = go.Figure()
    if kind == "site":
        n = max(len(sites), 1)
        scale = []
        for i in range(n):
            c = SITE_COLOURS[i % len(SITE_COLOURS)]
            scale += [[i / n, c], [(i + 1) / n, c]]
        shown = np.where(shown >= 0, shown, np.nan)
        fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=shown, colorscale=scale, zmin=-0.5, zmax=n - 0.5,
                        colorbar=dict(title=t("coverage.map.site"), tickvals=list(range(n)),
                                      ticktext=[s["candidate_id"] for s in sites]),
                        hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z}<extra></extra>")
    elif kind == "binary":
        fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=shown, colorscale=[[0, "#f2c7b8"], [1, "#256abf"]],
                        zmin=0, zmax=1, colorbar=dict(title="", tickvals=[0, 1],
                                                      ticktext=[t("coverage.map.not_covered"), t("coverage.map.covered")]),
                        hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z}<extra></extra>")
    else:
        lo, hi = zrange or default_range
        fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=shown, colorscale=SEQ, zmin=lo, zmax=hi,
                        colorbar=dict(title=unit), hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z:.1f} "
                        + unit + "<extra></extra>")
    if footprints is not None:
        xs, ys = outline_xy(footprints)
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color="#8a897f", width=0.6), fill="toself",
                        fillcolor="rgba(201,200,191,0.55)", hoverinfo="skip", showlegend=False,
                        name=t("common.show_buildings"))
    for i, s in enumerate(sites):
        c = SITE_COLOURS[i % len(SITE_COLOURS)]
        own = azimuths.get(s["candidate_id"], []) if isinstance(azimuths, dict) else azimuths
        for az in own or []:
            fig.add_scatter(x=[s["x"], s["x"] + 70 * np.cos(az)], y=[s["y"], s["y"] + 70 * np.sin(az)], mode="lines",
                            line=dict(color="#111", width=1.5), hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=[s["x"]], y=[s["y"]], mode="markers+text", text=[s["candidate_id"].replace("site-", "S")],
                        textposition="top right", marker=dict(symbol="triangle-up", size=13, color=c,
                                                               line=dict(color="#111", width=1)),
                        hovertext=t("coverage.map.site_hover", site=s["candidate_id"], building=s["building_id"],
                                    roof=f"{s['roof_height_m']:g}",
                                    category=t(f"common.height_category.{s['height_category']}"),
                                    antenna=f"{s['z']:g}"),
                        hoverinfo="text", showlegend=False)
    half = grid.cell_size_m / 2
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), title=dict(text=title, x=0.01, font_size=15),
                      plot_bgcolor="#e9e8e3", paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(title=t("coverage.map.x_axis"), range=[grid.x_centers[0] - half, grid.x_centers[-1] + half],
                                 showgrid=False, zeroline=False),
                      yaxis=dict(title=t("coverage.map.y_axis"), range=[grid.y_centers[0] - half, grid.y_centers[-1] + half],
                                 scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False))
    return fig


_ARABIC = __import__("re").compile(r"[؀-ۿ]")


def _isolate(text):
    """Arabic chart text inside a right-to-left isolate: Plotly draws in a left-to-right context, which
    would otherwise reorder mixed Arabic/Latin text such as 'وسيط SINR'."""
    if isinstance(text, str) and _ARABIC.search(text) and not text.startswith("⁧"):
        return f"⁧{text}⁩"
    return text


def chart(fig: go.Figure, container=None, **kwargs) -> None:
    """Show a Plotly figure; in Arabic its titles, axis titles, legend entries and annotations keep
    their reading order. Data, numbers and axes are unchanged."""
    if tr().rtl:
        layout = fig.layout
        if layout.title.text:
            layout.title.text = _isolate(layout.title.text)
        for axis in (layout.xaxis, layout.yaxis):
            if axis.title.text:
                axis.title.text = _isolate(axis.title.text)
        for trace in fig.data:
            if getattr(trace, "name", None):
                trace.name = _isolate(trace.name)
            bar = getattr(trace, "colorbar", None)
            if bar is not None and bar.title.text:
                bar.title.text = _isolate(bar.title.text)
            if getattr(trace, "colorbar", None) is not None and bar.ticktext:
                bar.ticktext = [_isolate(x) for x in bar.ticktext]
        for note in layout.annotations or ():
            note.text = _isolate(note.text)
    (container or st).plotly_chart(fig, use_container_width=True, **kwargs)


def fmt(value, spec: str, unit: str = "", scale: float = 1.0) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{value * scale:{spec}}{unit}"


def markdown_file(path) -> None:
    """Show a saved Markdown record: its label line as the banner, headings two levels smaller. Saved
    records are English documents; in Arabic a note says so."""
    from pathlib import Path as _P

    from bns.analysis import classification as cl

    lines = cl.display_text(_P(path).read_text(encoding="utf-8")).splitlines()
    markers = ("APPROVED", cl.PRELIMINARY, cl.BASELINE, cl.CUSTOM, cl.SENSITIVITY, cl.VALIDATED_RESULTS)
    if lines and lines[0].startswith("# ") and any(m in lines[0] for m in markers):
        result_banner(label_classification(lines[0][2:].strip()))       # the label line becomes the banner
        lines = lines[1:]
    if lang() != "en":
        st.caption(t("common.english_source"))
    st.markdown('<div dir="ltr" class="ltr">\n\n' + "\n".join("##" + ln if ln.startswith("#") else ln for ln in lines)
                + "\n\n</div>", unsafe_allow_html=True)


def band_name(label: str, frequency_ghz: float) -> str:
    """'4G LTE 1.8 GHz'; labels that already name their frequency are not repeated."""
    return label if "GHz" in label else f"{label} {frequency_ghz:g} GHz"


def visit(name: str) -> None:
    """Remember that the user opened a workflow page (drives the dashboard's next-step suggestion)."""
    st.session_state.setdefault("visited", set()).add(name)


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9α]+", "_", str(text).lower()).strip("_")


def localized_rows(rows: list[dict], value_columns: tuple[str, ...] = ("configuration", "use")) -> list[dict]:
    """Configuration table rows (bns.app.configuration) with translated column names, item labels and
    status values; technical values (numbers, identifiers, files) are kept as they are."""
    out = []
    for row in rows:
        new = {}
        for key, value in row.items():
            col = t(f"config.columns.{_slug(key)}") if tr().has(f"config.columns.{_slug(key)}") else key
            if key == "item" and tr().has(f"config.items.{_slug(value)}"):
                value = t(f"config.items.{_slug(value)}")
            elif key in value_columns and tr().has(f"config.values.{_slug(value)}"):
                value = t(f"config.values.{_slug(value)}")
            elif key == "value" and value is not None:
                value = str(value)              # mixed numbers and names: one text column
            new[col] = value
        out.append(new)
    return out
