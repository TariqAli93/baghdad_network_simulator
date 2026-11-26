import json
from datetime import datetime, timezone

import streamlit as st
import ui
import yaml

from bns.app import evidence

ui.page_header("6G roadmap for Iraq", "A structured workspace: verified facts, provisional results from saved runs, "
               "open questions, and your own recommendations. Nothing here is generated as a conclusion.")
st.markdown('<div class="dev-banner">Simulation evidence on this page comes from DEVELOPMENT runs — NOT APPROVED '
            "FOR RESEARCH. No date shown is a confirmed deployment date.</div>", unsafe_allow_html=True)

roadmap = yaml.safe_load((ui.ROOT / "configs" / "roadmap.yaml").read_text(encoding="utf-8"))
NOTES = ui.ROOT / "outputs" / "roadmap" / "student_recommendations.json"
try:
    notes = json.loads(NOTES.read_text(encoding="utf-8")) if NOTES.exists() else {}
except ValueError:
    notes = {}
    st.error(f"{NOTES} could not be read; it will be overwritten only when you save.")

runs = [ui.run(p) for p in ui.run_list() if not ui.run(p).invalid]          # invalidated runs are not evidence
networks = [r for r in runs if r.kind in ("multi_site", "single_site")]
plans = evidence.site_plans(ui.ROOT)
validation = evidence.validation_summary(ui.ROOT)


def result_block(metric: str) -> None:
    if metric == "band_comparison":
        if not networks:
            st.caption("No saved run yet.")
            return
        run = networks[0]
        st.caption(f"From `{run.run_id}` — {run.label}")
        st.dataframe([{"band": ui.band_name(r['scenario'], r['frequency_ghz']), "status": r["status"],
                       "coverage": ui.fmt(r["coverage"], ".1%"), "median SINR": ui.fmt(r["sinr_median_db"], ".1f", " dB"),
                       "5th-pct Shannon rate": ui.fmt(r["rate_p5_mbps"], ".0f", " Mbit/s")}
                      for r in evidence.band_table(run)], hide_index=True, use_container_width=True)
    elif metric == "site_density":
        if not plans:
            st.caption("No saved site plan yet (scripts/plan_sites.py).")
            return
        st.dataframe([{"band": ui.band_name(p['scenario'], p['frequency_ghz']), "threshold": f"{p['threshold_db']:g} dB",
                       "load": p["load"], "sites": p["sites"], "sites/km²": round(p["site_density_per_km2"], 1),
                       "coverage": ui.fmt(p["coverage"], ".1%"), "stop": p["stopped_because"],
                       "sensitivity case": "yes" if p["overrides"] else "no"} for p in plans],
                     hide_index=True, use_container_width=True)
        st.caption("Greedy over the saved candidates; not a minimum. 'Sensitivity case' rows use explicit, "
                   "unapproved threshold/load overrides.")
    elif metric == "validation":
        if validation is None:
            st.caption("No TR 38.901 comparison saved yet (scripts/validate_tr38901.py).")
            return
        st.caption(f"From `{validation['folder'].name}` (model-to-model comparison; not measurements)")
        st.dataframe([{**r, "mean_error_db": round(r["mean_error_db"], 1), "std_db": round(r["std_db"], 1),
                       "rmse_db": round(r["rmse_db"], 1)} for r in validation["rows"]],
                     hide_index=True, use_container_width=True)
    elif metric == "capacity_tradeoff":
        if not networks or not plans:
            st.caption("Needs a saved network run and a saved site plan.")
            return
        base = [p for p in plans if not p["overrides"]]
        sites = {p["scenario_id"]: p["sites"] for p in (base or plans)}
        st.dataframe([{"band": ui.band_name(r['scenario'], r['frequency_ghz']), "bandwidth": f"{r['bandwidth_mhz']:g} MHz",
                       "median Shannon rate": ui.fmt(r["rate_median_mbps"], ".0f", " Mbit/s"),
                       "sites selected (candidate assumptions)": sites.get(r["scenario_id"], "—")}
                      for r in evidence.band_table(networks[0])], hide_index=True, use_container_width=True)


KIND = {"verified": ("Verified evidence", "#1b7f5b"), "result": ("Provisional experimental result", "#c96a12"),
        "question": ("Open question", "#52514e")}
tabs = st.tabs([f"{i + 1}. {s['title']}" for i, s in enumerate(roadmap["stages"])])
for tab, stage in zip(tabs, roadmap["stages"], strict=True):
    with tab:
        st.markdown(f"*{stage['purpose'].strip()}*")
        for item in stage["items"]:
            name, colour = KIND[item["kind"]]
            src = f" — sources: {', '.join(f'`{s}`' for s in item.get('sources', []))}" if item.get("sources") else ""
            st.markdown(f'<div style="border-left:3px solid {colour};padding:.2rem .7rem;margin:.5rem 0">'
                        f'<span style="font-size:.75rem;color:{colour};font-weight:600">{name}</span><br>'
                        f'{item["text"].strip()}{src}</div>', unsafe_allow_html=True)
            if item["kind"] == "result":
                result_block(item["metric"])
        st.markdown("**Your recommendations for this stage** (stored locally; not generated)")
        text = st.text_area("Recommendation", value=notes.get(stage["id"], {}).get("text", ""), height=140,
                            key=f"note-{stage['id']}", label_visibility="collapsed",
                            placeholder="Write your interpretation and recommendation, citing the evidence above.")
        if st.button("Save", key=f"save-{stage['id']}"):
            notes[stage["id"]] = {"text": text, "saved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            NOTES.parent.mkdir(parents=True, exist_ok=True)
            NOTES.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Saved.")
        if stage["id"] in notes:
            st.caption(f"Last saved {notes[stage['id']]['saved_utc']}")

st.divider()
st.subheader("Assumptions and limitations")
for line in ("The simulation district, building heights, radio parameters and site rule are not approved (A1-A4).",
             "Shannon rates are theoretical upper bounds for one user with the whole carrier.",
             "8 and 15 GHz are candidate research bands (WRC-27 studies), not finalized 6G specifications.",
             "Press-based facts about Iraq's 5G status rest on few sources and must be re-checked before submission."):
    st.markdown(f"- {line}")
