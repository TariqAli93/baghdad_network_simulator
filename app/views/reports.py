import io
import zipfile

import streamlit as st
import ui
from ui import t

from bns import i18n
from bns.app import evidence
from bns.reporting.report import build_html, limitations, value_source as report_value_source

ui.page_header("reports.title", "reports.caption")
ui.visit("reports")
tr = ui.tr()
run = ui.pick_run("report-run", kinds=("single_site", "multi_site", "site_plan"))
if run is None:
    st.stop()
ui.result_banner(run.classification)
m = run.manifest
if "gba" in str(m["area"].get("variant", "")).lower():
    st.warning(t("reports.gba_licence"))
validation = evidence.validation_summary(ui.ROOT)

# the printable report first: it is what most visitors of this page come for
st.subheader(t("reports.printable"))
p1, p2, _ = st.columns([2, 2, 3], vertical_alignment="bottom")
with p1:
    report_lang = st.segmented_control(t("reports.report_language"), list(i18n.LANGUAGES), default=ui.lang(),
                                       key="report-lang",
                                       format_func=lambda code: i18n.translate(code, f"common.language_names.{code}"))
report_lang = report_lang or ui.lang()
extra = {i18n.translate(report_lang, "report.validation_extra"):
         (validation["folder"] / "summary.md").read_text(encoding="utf-8")} if validation else {}
html = build_html(run.path, extra_markdown=extra, invalid_reason=run.invalid, lang=report_lang)
with p2:
    st.download_button(t("reports.download_report"), html.encode("utf-8"), type="primary",
                       file_name=f"report-{run.run_id}-{report_lang}.html", mime="text/html")
st.caption(t("reports.report_note"))


def table(rows: list[tuple[str, str]]) -> None:
    """A two-column key/value table; values (identifiers, numbers) stay left-to-right."""
    st.markdown("<table class='kv'>" + "".join(f"<tr><th>{k}</th><td>{ui.ltr(v)}</td></tr>" for k, v in rows)
                + "</table>", unsafe_allow_html=True)


area = m["area"]
versions = m.get("versions") or {}
overrides = m.get("overrides") or {}
c1, c2 = st.columns(2)
with c1:
    st.subheader(t("reports.configuration"))
    R = "reports.rows."
    table([(t(R + "run"), run.run_id), (t(R + "kind"), f"{run.kind} / {m.get('mode')}"),
           (t(R + "area"), f"{area['name']} / {area.get('variant')} — {t('common.area_role.' + area['role'])}"
            if area.get("role") in ("study district", "provisional study area", "development fixture")
            else f"{area['name']} / {area.get('variant')}"),
           (t(R + "profile"), t("simulation.profile_option", name=m["profile"]["name"],
                                cell=f"{m['profile']['cell_size_m']:g}", rays=f"{m['profile']['rays_per_site']:.0e}")),
           (t(R + "backend"), f"{run.backend} ({(m.get('backend') or {}).get('status', 'production')})"),
           (t(R + "sites"), t("common.candidates", count=len(run.sites)) if run.kind == "site_plan"
            else t("common.sites", count=len(run.sites))),
           (t(R + "deviations"), "; ".join((m.get("classification") or {}).get("deviations") or [])
            if run.is_workspace else ", ".join(f"{k} = {v}" for k, v in overrides.items())
            or (t("report.none") if "overrides" in m else t("report.not_recorded")))])
with c2:
    st.subheader(t("reports.provenance"))
    table([(t(R + "osm"), f"{str(area.get('osm_snapshot_sha256', ''))[:24]}…"),
           (t(R + "scene"), f"{str(area.get('scene_fingerprint', ''))[:24]}…"),
           (t(R + "categories"), ", ".join(f"{k} {v:.1f} %" for k, v in (area.get("height_categories_percent") or {}).items())),
           (t(R + "fit"), t("common.yes_word") if area.get("fit_for_research") else t("common.no_word")),
           (t(R + "engine"), f"Sionna RT {versions.get('sionna-rt', '?')}, Mitsuba {versions.get('mitsuba', '?')}")])

st.subheader(t("report.radio"))
params = m.get("radio_parameters") or {}
C = "report.radio_columns."
st.dataframe([{t(C + "parameter"): k, t(C + "value"): str(v.get("value") if isinstance(v, dict) else v),
               t("config.columns.unit"): (v.get("unit") or "") if isinstance(v, dict) else "",
               t(C + "source"): report_value_source(m, k, ui.lang())} for k, v in params.items()],
             hide_index=True, use_container_width=True)

st.subheader(t("reports.statistics"))
names = {s["id"]: ui.scenario_name(s) for s in run.scenarios}
S = "reports.stats."
st.dataframe([{t("comparison.columns.scenario"): names.get(r["scenario_id"], r["scenario"]),   # name carries GHz
               t(S + "coverage"): ui.fmt(r["coverage"], ".1%"),
               t(S + "rx_power"): ui.fmt(r["rx_power_median_dbm"], ".1f", " dBm"),
               t(S + "sinr_median"): ui.fmt(r["sinr_median_db"], ".1f", " dB"),
               t(S + "sinr_p5"): ui.fmt(r["sinr_p5_db"], ".1f", " dB"),
               t(S + "rate_p5"): ui.fmt(r["rate_p5_mbps"], ".1f", " Mbit/s"),
               t(S + "rate_median"): ui.fmt(r["rate_median_mbps"], ".0f", " Mbit/s")} for r in evidence.band_table(run)],
             hide_index=True, use_container_width=True)
st.caption(t("common.units_note"))

if run.kind == "site_plan":
    st.subheader(t("reports.plan"))
    P = "planning.columns."
    st.dataframe([{t(P + "scenario"): names.get(sid, sid), t(P + "selected"): ", ".join(r["selected"]),
                   t("comparison.plans.columns.sites"): r["sites"],
                   t("comparison.plans.columns.coverage"): ui.fmt((r["coverage_after"] or [None])[-1], ".1%"),
                   t(P + "stop"): ui.recorded(r["stopped_because"]), t(P + "uncovered"): r["uncovered_outdoor_cells"],
                   t("comparison.plans.columns.density"): round(r["site_density_per_km2"], 1)}
                  for sid, r in run.summary["results"].items()], hide_index=True, use_container_width=True)

with st.expander(t("reports.validation")):
    if validation is None:
        st.caption(t("reports.none_saved"))
    else:
        ui.markdown_file(validation["folder"] / "summary.md")

notes = {name: run.path / name for name in ("summary.md", "sensitivity.md", "backend_agreement.md",
                                            "near_site_nr_28000.md") if (run.path / name).exists()}
for name, path in notes.items():
    with st.expander(t("reports.note", name=name)):
        ui.markdown_file(path)

pngs = sorted(run.path.glob("*.png"))
if pngs:
    st.subheader(t("reports.figures"))
    pick = st.selectbox(t("reports.figure"), pngs, format_func=lambda p: p.name)
    st.image(str(pick))
    if "classification" not in run.manifest:
        st.caption(t("report.old_figures"))
    if ui.lang() != "en":
        st.caption(t("report.figures_english"))
    st.download_button(t("reports.download_figure"), pick.read_bytes(), file_name=pick.name, mime="image/png")
else:
    st.caption(t("reports.no_figures"))

st.subheader(t("reports.exports"))
csvs = sorted(run.path.glob("*.csv"))
e1, e2 = st.columns(2)
with e1:
    st.markdown(f"**{t('reports.data')}**")
    if not csvs:
        st.caption(t("reports.no_csv"))
    for p in csvs:
        st.download_button(p.name, p.read_bytes(), file_name=p.name, mime="text/csv", key=f"csv-{p.name}")
with e2:
    st.markdown(f"**{t('reports.reproducibility')}**")
    st.download_button("manifest.json", (run.path / "manifest.json").read_bytes(), file_name="manifest.json",
                       mime="application/json")
    st.download_button("summary.json", (run.path / "summary.json").read_bytes(), file_name="summary.json",
                       mime="application/json")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in run.path.iterdir():
            if p.is_file() and p.suffix != ".npz":
                z.write(p, p.name)
    st.download_button(t("reports.zip"), buf.getvalue(), file_name=f"{run.run_id}.zip", mime="application/zip")
    st.caption(t("reports.machine_readable"))

st.subheader(t("reports.limitations"))
for line in limitations(ui.lang()):
    st.markdown(f"- {line}")
