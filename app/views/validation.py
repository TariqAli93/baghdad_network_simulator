import json

import streamlit as st
import ui

ui.page_header("Validation", "Engine checks against closed-form references (Phase 0) and the ray-count "
               "convergence behind the profiles. External verification against MATLAB is planned, not done.")

st.subheader("Phase 0 engine experiments")
rows = []
for e in ("e1", "e2", "e3", "e4", "e5"):
    path = ui.ROOT / "outputs" / "runs" / "phase0" / e / "result.json"
    if path.exists():
        r = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"experiment": r.get("experiment", e.upper()), "passed": r.get("passed"),
                     "note": " ".join(str(r.get("note", "")).split())[:200]})
    else:
        pngs = sorted((ui.ROOT / "outputs" / "runs" / "phase0" / e).glob("*.png"))
        rows.append({"experiment": e.upper(), "passed": None,
                     "note": "reported for judgement (no pass/fail)" if pngs else "not run"})
st.dataframe(rows, hide_index=True, use_container_width=True)
for e in ("e1", "e2", "e3", "e5"):
    pngs = sorted((ui.ROOT / "outputs" / "runs" / "phase0" / e).glob("*.png"))
    if pngs:
        with st.expander(f"{e.upper()} figure"):
            st.image(str(pngs[0]))

st.subheader("Convergence (profiles)")
path = ui.ROOT / "outputs" / "runs" / "convergence" / "tahrir_bab_al_sharqi_v2" / "summary.md"
st.markdown(path.read_text(encoding="utf-8") if path.exists() else "No convergence run found.")
