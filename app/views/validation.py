import json
import re

import streamlit as st
import ui
from ui import t

from bns.app import evidence

ui.page_header("validation.title", "validation.caption")
ui.visit("limitations")
V = "validation.categories."


def bold(text: str) -> str:
    """Markdown **bold** as HTML: inside an HTML table cell Markdown is not rendered."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


st.markdown("<table class='kv'>" + "".join(
    f"<tr><th>{t(V + k + '.name')}</th><td>{bold(t(V + k + '.status'))}</td></tr>"
    for k in ("analytical", "model", "matlab", "field")) + "</table>", unsafe_allow_html=True)

st.subheader(t("validation.tr38901"))
v = evidence.validation_summary(ui.ROOT)
if v is None:
    st.info(t("validation.tr38901_none"))
else:
    ui.markdown_file(v["folder"] / "summary.md")
    for png in ("pathloss_UMa.png", "pathloss_UMi.png", "los_probability.png"):
        if (v["folder"] / png).exists():
            st.image(str(v["folder"] / png))
    st.caption(t("report.old_figures"))

st.subheader(t("validation.engine"))
rows = []
C = "validation.columns."
for e in ("e1", "e2", "e3", "e4", "e5"):
    path = ui.ROOT / "outputs" / "runs" / "phase0" / e / "result.json"
    if path.exists():
        r = json.loads(path.read_text(encoding="utf-8"))
        passed = r.get("passed")
        rows.append({t(C + "experiment"): r.get("experiment", e.upper()),
                     t(C + "passed"): "—" if passed is None else t("common.yes_word") if passed else t("common.no_word"),
                     t(C + "note"): " ".join(str(r.get("note", "")).split())[:200]})
    else:
        rows.append({t(C + "experiment"): e.upper(), t(C + "passed"): "—", t(C + "note"): t("validation.judgement")})
st.dataframe(rows, hide_index=True, use_container_width=True)
if ui.lang() != "en":
    st.caption(t("validation.notes_english"))

st.subheader(t("validation.near_site"))
for run in (ui.run(p) for p in ui.run_list()):
    note = run.path / "near_site_nr_28000.md"
    if note.exists():
        with st.expander(t("validation.diagnosis", run=run.run_id)):
            ui.markdown_file(note)
        break
for folder in sorted((ui.ROOT / "outputs" / "runs" / "development").glob("antenna_placement-*"), reverse=True)[:1]:
    with st.expander(t("validation.experiment", name=folder.name)):
        ui.markdown_file(folder / "summary.md")

st.subheader(t("validation.backends"))
for run in (ui.run(p) for p in ui.run_list()):
    note = run.path / "backend_agreement.md"
    if note.exists():
        ui.markdown_file(note)
        break
else:
    st.caption(t("validation.no_backends"))

st.subheader(t("validation.matlab"))
cases = sorted((ui.ROOT / "validation" / "matlab").glob("*/case.json"))
if not cases:
    st.caption(t("validation.no_matlab"))
for case in cases:
    folder = case.parent
    done = (folder / "comparison.md").exists()
    st.markdown(f"**{folder.name}** — {t('validation.compared') if done else t('validation.prepared')}")
    ui.markdown_file(folder / ("comparison.md" if done else "README.md"))

st.subheader(t("validation.convergence"))
path = ui.ROOT / "outputs" / "runs" / "convergence" / "tahrir_bab_al_sharqi_v2" / "summary.md"
if path.exists():
    ui.markdown_file(path)
else:
    st.caption(t("validation.no_convergence"))
