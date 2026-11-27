import json
from datetime import datetime, timezone

import streamlit as st
import ui
import yaml
from ui import t

from bns import i18n
from bns.app import evidence

ui.page_header("roadmap.title", "roadmap.caption")
tr = ui.tr()
st.markdown(f'<div class="result-banner"><b>{t("roadmap.banner")}</b><span>{t("roadmap.banner_detail")}</span></div>',
            unsafe_allow_html=True)

roadmap = yaml.safe_load((ui.ROOT / "configs" / "roadmap.yaml").read_text(encoding="utf-8"))
NOTES = ui.ROOT / "outputs" / "roadmap" / "student_recommendations.json"
try:
    notes = json.loads(NOTES.read_text(encoding="utf-8")) if NOTES.exists() else {}
except ValueError:
    notes = {}
    st.error(t("roadmap.unreadable", path=NOTES.name))

runs = [ui.run(p) for p in ui.run_list() if not ui.run(p).invalid]          # invalidated runs are not evidence
networks = [r for r in runs if r.kind in ("multi_site", "single_site")]
plans = evidence.site_plans(ui.ROOT)
validation = evidence.validation_summary(ui.ROOT)
by_freq = {round(s["frequency_hz"] / 1e9, 3): ui.scenario_name(s) for s in ui.scenarios()}
statuses = {s["id"]: ui.scenario_status(s) for s in ui.scenarios()}


def band(row: dict) -> str:
    return by_freq.get(round(row["frequency_ghz"], 3), ui.band_name(row["scenario"], row["frequency_ghz"]))


def result_block(metric: str) -> None:
    C = "roadmap.columns."
    if metric == "band_comparison":
        if not networks:
            st.caption(t("roadmap.no_run"))
            return
        run = networks[0]
        head, details = i18n.classification_texts(tr, run.classification)
        st.caption(t("roadmap.from_run", run=run.run_id, label=head))
        st.dataframe([{t(C + "band"): band(r), t(C + "status"): statuses.get(r["scenario_id"], r["status"]),
                       t(C + "coverage"): ui.fmt(r["coverage"], ".1%"),
                       t(C + "sinr"): ui.fmt(r["sinr_median_db"], ".1f", " dB"),
                       t(C + "rate_p5"): ui.fmt(r["rate_p5_mbps"], ".0f", " Mbit/s")}
                      for r in evidence.band_table(run)], hide_index=True, use_container_width=True)
    elif metric == "site_density":
        if not plans:
            st.caption(t("roadmap.no_plan"))
            return
        st.dataframe([{t(C + "band"): band(p), t(C + "threshold"): f"{p['threshold_db']:g} dB",
                       t(C + "load"): p["load"], t(C + "sites"): p["sites"],
                       t(C + "density"): round(p["site_density_per_km2"], 1),
                       t(C + "coverage"): ui.fmt(p["coverage"], ".1%"), t(C + "stop"): ui.recorded(p["stopped_because"]),
                       t(C + "sensitivity"): t("common.yes_word") if p["overrides"] else t("common.no_word")}
                      for p in plans], hide_index=True, use_container_width=True)
        st.caption(t("roadmap.plan_note"))
    elif metric == "validation":
        if validation is None:
            st.caption(t("comparison.model.none"))
            return
        st.caption(t("roadmap.from_validation", folder=validation["folder"].name))
        st.dataframe([{**r, "mean_error_db": round(r["mean_error_db"], 1), "std_db": round(r["std_db"], 1),
                       "rmse_db": round(r["rmse_db"], 1)} for r in validation["rows"]],
                     hide_index=True, use_container_width=True)
    elif metric == "capacity_tradeoff":
        if not networks or not plans:
            st.caption(t("roadmap.needs_both"))
            return
        base = [p for p in plans if not p["overrides"]]
        sites = {p["scenario_id"]: p["sites"] for p in (base or plans)}
        st.dataframe([{t(C + "band"): band(r), t(C + "bandwidth"): f"{r['bandwidth_mhz']:g} MHz",
                       t(C + "rate_median"): ui.fmt(r["rate_median_mbps"], ".0f", " Mbit/s"),
                       t(C + "selected"): sites.get(r["scenario_id"], "—")}
                      for r in evidence.band_table(networks[0])], hide_index=True, use_container_width=True)


COLOURS = {"verified": "#1b7f5b", "result": "#c96a12", "question": "#52514e"}


def text_of(stage: str, n: int, item: dict) -> str:
    key = f"roadmap.items.{stage}.i{n}"
    return t(key) if tr.has(key) else " ".join(item["text"].split())


tabs = st.tabs([f"{i + 1}. {t('roadmap.stages.' + s['id'] + '.title')}" for i, s in enumerate(roadmap["stages"])])
for tab, stage in zip(tabs, roadmap["stages"], strict=True):
    with tab:
        st.markdown(f"*{t('roadmap.stages.' + stage['id'] + '.purpose')}*")
        for n, item in enumerate(stage["items"]):
            colour = COLOURS[item["kind"]]
            src = (f" — {t('roadmap.sources')}: " + ", ".join(f"<code>{s}</code>" for s in item["sources"])
                   if item.get("sources") else "")
            st.markdown(f'<div style="border-inline-start:3px solid {colour};padding:.2rem .7rem;margin:.5rem 0">'
                        f'<span style="font-size:.75rem;color:{colour};font-weight:600">'
                        f'{t("roadmap.kinds." + item["kind"])}</span><br>{text_of(stage["id"], n, item)}{src}</div>',
                        unsafe_allow_html=True)
            if item["kind"] == "result":
                result_block(item["metric"])
        st.markdown(t("roadmap.your_notes"))
        text = st.text_area(t("roadmap.recommendation"), value=notes.get(stage["id"], {}).get("text", ""), height=140,
                            key=f"note-{stage['id']}", label_visibility="collapsed",
                            placeholder=t("roadmap.placeholder"))
        if st.button(t("roadmap.save"), key=f"save-{stage['id']}"):
            notes[stage["id"]] = {"text": text, "saved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            NOTES.parent.mkdir(parents=True, exist_ok=True)
            NOTES.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success(t("roadmap.saved"))
        if stage["id"] in notes:
            st.caption(t("roadmap.last_saved", date=tr.date(notes[stage["id"]]["saved_utc"])))

st.divider()
st.subheader(t("roadmap.assumptions"))
for key in ("dataset", "shannon", "bands", "press"):
    st.markdown(f"- {t('roadmap.limits.' + key)}")
