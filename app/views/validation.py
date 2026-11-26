import json

import streamlit as st
import ui

from bns.app import evidence

ui.page_header("Validation", "What has been checked, and how. Four categories are kept apart: (1) analytical "
               "verification, (2) model-to-model comparison, (3) MATLAB cross-check, (4) field measurements.")
st.markdown("""
| Category | Status |
|---|---|
| 1. Analytical verification (engine vs closed form) | **done**: Phase 0 E1-E3, pipeline tests, antenna pattern, near-site check |
| 2. Model-to-model (ray tracing vs 3GPP TR 38.901) | **done** for a controlled configuration (below) |
| 3. MATLAB cross-check | **prepared, not executed** (package in `validation/matlab/`) |
| 4. Field measurements | **none** in this project |
""")

st.subheader("2. Ray tracing vs 3GPP TR 38.901 (UMa, UMi)")
v = evidence.validation_summary(ui.ROOT)
if v is None:
    st.info("Not run yet: `uv run python scripts/validate_tr38901.py --area tahrir_bab_al_sharqi_v2`.")
else:
    ui.markdown_file(v["folder"] / "summary.md")
    for png in ("pathloss_UMa.png", "pathloss_UMi.png", "los_probability.png"):
        if (v["folder"] / png).exists():
            st.image(str(v["folder"] / png))

st.subheader("Engine checks (Phase 0)")
rows = []
for e in ("e1", "e2", "e3", "e4", "e5"):
    path = ui.ROOT / "outputs" / "runs" / "phase0" / e / "result.json"
    if path.exists():
        r = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"experiment": r.get("experiment", e.upper()), "passed": r.get("passed"),
                     "note": " ".join(str(r.get("note", "")).split())[:200]})
    else:
        rows.append({"experiment": e.upper(), "passed": None, "note": "reported for judgement (no pass/fail)"})
st.dataframe(rows, hide_index=True, use_container_width=True)

st.subheader("Near-site coverage gap (28 GHz) and the antenna-position experiment")
for run in (ui.run(p) for p in ui.run_list()):
    note = run.path / "near_site_nr_28000.md"
    if note.exists():
        with st.expander(f"Diagnosis on `{run.run_id}`"):
            ui.markdown_file(note)
        break
for folder in sorted((ui.ROOT / "outputs" / "runs" / "development").glob("antenna_placement-*"), reverse=True)[:1]:
    with st.expander(f"Controlled experiment `{folder.name}`"):
        ui.markdown_file(folder / "summary.md")

st.subheader("CPU and GPU backends")
for run in (ui.run(p) for p in ui.run_list()):
    note = run.path / "backend_agreement.md"
    if note.exists():
        ui.markdown_file(note)
        break
else:
    st.caption("No CPU/GPU comparison saved.")

st.subheader("3. MATLAB cross-check package")
cases = sorted((ui.ROOT / "validation" / "matlab").glob("*/case.json"))
if not cases:
    st.caption("No package prepared (`scripts/export_matlab_case.py`).")
for case in cases:
    folder = case.parent
    done = (folder / "comparison.md").exists()
    st.markdown(f"**{folder.name}** — {'compared' if done else 'prepared, not executed'}")
    ui.markdown_file(folder / ("comparison.md" if done else "README.md"))

st.subheader("Convergence (profiles)")
path = ui.ROOT / "outputs" / "runs" / "convergence" / "tahrir_bab_al_sharqi_v2" / "summary.md"
if path.exists():
    ui.markdown_file(path)
else:
    st.caption("No convergence run found.")
