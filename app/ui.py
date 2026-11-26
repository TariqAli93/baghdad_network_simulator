"""Shared Streamlit helpers: labels, cached loaders and the map figure.

UI code only. Every number shown comes from saved runs, configuration files or
the bns package; nothing scientific is computed here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml

from bns.app import results
from bns.reporting import plotstyle as style

ROOT = Path(__file__).resolve().parents[1]
DEV_LABEL = "DEVELOPMENT — NOT APPROVED FOR RESEARCH"
SEQ = [[i / 6, c] for i, c in enumerate(["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])]
SITE_COLOURS = ["#2a6f97", "#c0504d", "#5b8c3a", "#8064a2", "#d08c2b", "#4b9b9b", "#7a6a53", "#b5527a"]
CATEGORY_COLOURS = {"observed": "#1b7f5b", "estimated": "#d08c2b", "placeholder": "#b9b8b0"}

LAYERS = {   # name in the saved arrays -> (title, unit, colour range, kind)
    "path_gain_db": ("Path gain, best sector (propagation only)", "dB", (-160, -60), "seq"),
    "rx_power_dbm": ("Received power, serving sector", "dBm", (-120, -20), "seq"),
    "sinr_db": ("SINR", "dB", (-10, 40), "seq"),
    "rate_bps": ("Shannon rate (upper bound)", "Mbit/s", None, "rate"),
    "rate_3gpp_bps": ("3GPP truncated rate (TR 38.921, beside Shannon)", "Mbit/s", None, "rate"),
    "covered": ("Coverage (SINR at or above threshold)", "", (0, 1), "binary"),
    "serving_site": ("Serving site", "", None, "site"),
    "interference_dbm": ("Interference power (all non-serving sectors)", "dBm", (-130, -50), "seq"),
}


def page_header(title: str, caption: str) -> None:
    st.title(title)
    st.caption(caption)


def development_banner(label: str | None = DEV_LABEL) -> None:
    if label and "NOT APPROVED" in label:
        st.markdown(f'<div class="dev-banner">{label}</div>', unsafe_allow_html=True)
    elif label:
        st.success(label)


def inject_css() -> None:
    st.markdown("""
<style>
div.block-container, [data-testid="stMainBlockContainer"] {padding-top: 2.2rem;}
.dev-banner {border-left: 4px solid #c96a12; background: #fff4e5; color: #6b3a06; padding: .45rem .8rem;
             font-weight: 600; letter-spacing: .02em; border-radius: 4px; margin: .2rem 0 .8rem 0;}
div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
section[data-testid="stSidebar"] .sidebar-note {font-size: .8rem; color: #52514e;}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def scenarios() -> list[dict]:
    from bns.simulation.experiment import load_scenarios
    return load_scenarios(ROOT)


def colour(scenario_id: str) -> str:
    return style.SCENARIO_COLORS.get(scenario_id, style.INK_SECONDARY)


@st.cache_data(show_spinner=False)
def study_areas() -> dict:
    return yaml.safe_load((ROOT / "configs" / "study_area.yaml").read_text(encoding="utf-8"))["areas"]


def variants(area: str) -> list[str]:
    folder = ROOT / "data" / "scenes" / area
    return sorted(d.name for d in folder.iterdir() if (d / "scene.xml").exists()) if folder.exists() else []


@st.cache_resource(show_spinner="Loading buildings...")
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


@st.cache_resource(show_spinner="Loading run...", max_entries=6)
def run(path: str) -> results.Run:
    return results.load_run(Path(path))


def run_title(r: results.Run) -> str:
    m = r.manifest
    sites = len(r.sites)
    return (f"{m.get('created_utc', '')[:16].replace('T', ' ')} · {'multi' if r.kind == 'multi_site' else 'single'}-site "
            f"({sites} site{'s' if sites != 1 else ''}) · {m['profile']['name']} · {m['area']['name']}/{m['area'].get('variant', '')}")


def pick_run(key: str, *, kinds: tuple[str, ...] = ("single_site", "multi_site")) -> results.Run | None:
    paths = [p for p in run_list() if run(p).kind in kinds]
    if not paths:
        st.info("No saved run of this kind yet. Start one on the **Simulation** page "
                "(or with `scripts/run_multi_site.py`).")
        return None
    chosen = st.selectbox("Saved run", paths, format_func=lambda p: run_title(run(p)), key=key)
    return run(chosen)


def map_figure(grid, z, outdoor, *, layer: str, sites: list[dict], azimuths: list[float] | None = None,
               footprints=None, height: int = 620, zrange=None) -> go.Figure:
    title, unit, default_range, kind = LAYERS.get(layer, (layer, "", None, "seq"))
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
                        colorbar=dict(title="site", tickvals=list(range(n)),
                                      ticktext=[s["candidate_id"] for s in sites]),
                        hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>site index %{z}<extra></extra>")
    elif kind == "binary":
        fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=shown, colorscale=[[0, "#f2c7b8"], [1, "#256abf"]],
                        zmin=0, zmax=1, colorbar=dict(title="", tickvals=[0, 1], ticktext=["not covered", "covered"]),
                        hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z}<extra></extra>")
    else:
        lo, hi = zrange or default_range
        fig.add_heatmap(x=grid.x_centers, y=grid.y_centers, z=shown, colorscale=SEQ, zmin=lo, zmax=hi,
                        colorbar=dict(title=unit), hovertemplate="x %{x:.0f} m, y %{y:.0f} m<br>%{z:.1f} "
                        + unit + "<extra></extra>")
    if footprints is not None:
        xs, ys = outline_xy(footprints)
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color="#8a897f", width=0.6), fill="toself",
                        fillcolor="rgba(201,200,191,0.55)", hoverinfo="skip", showlegend=False, name="buildings")
    for i, s in enumerate(sites):
        c = SITE_COLOURS[i % len(SITE_COLOURS)]
        for az in azimuths or []:
            fig.add_scatter(x=[s["x"], s["x"] + 70 * np.cos(az)], y=[s["y"], s["y"] + 70 * np.sin(az)], mode="lines",
                            line=dict(color="#111", width=1.5), hoverinfo="skip", showlegend=False)
        fig.add_scatter(x=[s["x"]], y=[s["y"]], mode="markers+text", text=[s["candidate_id"].replace("site-", "S")],
                        textposition="top right", marker=dict(symbol="triangle-up", size=13, color=c,
                                                               line=dict(color="#111", width=1)),
                        hovertext=f"{s['candidate_id']} on {s['building_id']}<br>roof {s['roof_height_m']:g} m "
                                  f"({s['height_category']}), antenna {s['z']:g} m",
                        hoverinfo="text", showlegend=False)
    half = grid.cell_size_m / 2
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), title=dict(text=title, x=0.01, font_size=15),
                      plot_bgcolor="#e9e8e3", paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(title="x east [m]", range=[grid.x_centers[0] - half, grid.x_centers[-1] + half],
                                 showgrid=False, zeroline=False),
                      yaxis=dict(title="y north [m]", range=[grid.y_centers[0] - half, grid.y_centers[-1] + half],
                                 scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False))
    return fig


def fmt(value, spec: str, unit: str = "", scale: float = 1.0) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{value * scale:{spec}}{unit}"


def markdown_file(path) -> None:
    """Show a saved Markdown note: its label line as the banner, headings two levels smaller."""
    from pathlib import Path as _P

    lines = _P(path).read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# ") and "APPROVED" in lines[0]:
        development_banner(lines[0][2:].strip())
        lines = lines[1:]
    st.markdown("\n".join("##" + ln if ln.startswith("#") else ln for ln in lines))


def band_name(label: str, frequency_ghz: float) -> str:
    """'4G LTE 1.8 GHz'; labels that already name their frequency are not repeated."""
    return label if "GHz" in label else f"{label} {frequency_ghz:g} GHz"
