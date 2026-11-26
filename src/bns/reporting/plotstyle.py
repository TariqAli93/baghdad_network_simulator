"""One visual style for every chart the project produces.

Colour follows the entity, never its position in a plot: each radio scenario
keeps the same colour in every figure. Magnitude uses a single-hue ramp and
signed error uses two hues around a neutral midpoint.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # files only; no window is ever opened

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Fixed categorical order (validated for adjacent-series separation, including
# colour-vision deficiency). Scenario ids come from configs/scenarios.yaml.
SCENARIO_COLORS = {
    "lte_1800": "#2a78d6",    # blue
    "nr_3500": "#eb6834",     # orange
    "c6g_8000": "#1baf7a",    # aqua
    "c6g_15000": "#eda100",   # yellow
    "nr_28000": "#e87ba4",    # magenta
}
NEUTRAL_SERIES = INK_SECONDARY   # reference curves (theory), drawn dashed

SEQUENTIAL = LinearSegmentedColormap.from_list(
    "bns_sequential",
    ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
SEQUENTIAL.set_bad("#e9e8e3")    # masked cells (indoor / no path) are neutral, not "low"

DIVERGING = LinearSegmentedColormap.from_list(
    "bns_diverging", ["#2a78d6", "#f0efec", "#e34948"])
DIVERGING.set_bad("#e9e8e3")


def apply() -> None:
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "text.color": INK,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "legend.frameon": False,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def label_line_end(ax, x, y, text: str, side: str = "right") -> None:
    """Name a series at one of its ends so identity never rests on colour alone."""
    offset, align = ((6, 0), "left") if side == "right" else ((-6, 0), "right")
    ax.annotate(text, (x, y), xytext=offset, textcoords="offset points",
                va="center", ha=align, fontsize=9, color=INK_SECONDARY, clip_on=False)
