"""Experiment History: saved experiments (editable configurations), completed runs (immutable results)
and the simulations running or stopped in the background.

Every action here goes through bns.app (experiments, results, workspace_runs, control); opening an
experiment or a run moves to the Simulation Workspace, viewing a run to the run viewer, a report to
the Reports page.
"""

import streamlit as st
import ui
from ui import t

from bns.app import control, results
from bns.app import experiments as xp
from bns.app import workspace_runs as wr

ui.page_header("history.title", "history.caption")
SS = st.session_state
ROOT = ui.ROOT
tr = ui.tr()


def when(text: str) -> str:
    return tr.date(text) if text else "—"


def head(run: results.Run) -> str:
    from bns import i18n

    h_, _ = i18n.classification_texts(tr, run.classification)
    key = {"Automatic placement": "automatic", "Manual placement": "manual",
           "Hypothetical placement": "hypothetical"}.get(run.classification.placement)
    return h_ + (f" · {t('cls.placements.' + key)}" if key else "")


def open_in_workspace(**request) -> None:
    SS["w_request"] = request
    st.switch_page("views/workspace.py")


@st.dialog(t("history.delete_title"))
def confirm_delete(e: xp.Experiment) -> None:
    st.markdown(t("history.delete_text", name=e.name, runs=len(xp.runs_of(ROOT, e.experiment_id))))
    a, b = st.columns(2)
    if a.button(t("workspace.experiment.delete_confirm"), type="primary", width="stretch"):
        xp.delete(ROOT, e.experiment_id)
        if (SS.get("w_meta") or {}).get("experiment_id") == e.experiment_id:
            SS["w_saved_sig"] = None                # the workspace copy becomes an unsaved experiment
        st.rerun()
    if b.button(t("workspace.experiment.cancel"), width="stretch"):
        st.rerun()


# ---------------------------------------------------------------- experiments
st.subheader(t("history.experiments"))
experiments = xp.list_all(ROOT)
active = wr.active(ROOT)
if not experiments:
    st.caption(t("history.no_experiments"))
else:
    rows = []
    for e in experiments:
        runs = xp.runs_of(ROOT, e.experiment_id)
        running = active is not None and (active.request.get("experiment") or {}).get("id") == e.experiment_id
        state = "Running" if running else ("Completed" if runs else "Ready")
        on = [c for c in e.carriers if c.get("selected", True)]
        rows.append({t("history.columns.name"): e.name, t("history.columns.modified"): when(e.modified_utc),
                     t("history.columns.dataset"): f"{e.area}/{e.variant}",
                     t("history.columns.stations"): sum(1 for s in e.stations if s.get("enabled", True)),
                     t("history.columns.carriers"): ", ".join(f"{c['frequency_hz'] / 1e9:g}" for c in on) + " GHz",
                     t("history.columns.profile"): f"{e.profile} · {e.backend.upper()}",
                     t("history.columns.runs"): len(runs),
                     t("history.columns.state"): t(f"history.execution.{state.lower()}")})
    picked = st.dataframe(rows, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                          key="h_experiments")
    chosen = picked.selection.rows[0] if picked is not None and picked.selection.rows else None
    if chosen is None:
        st.caption(t("history.pick_experiment"))
    else:
        e = experiments[chosen]
        c1, c2, c3, c4 = st.columns(4)
        if c1.button(t("history.open"), type="primary", width="stretch"):
            open_in_workspace(experiment=e.experiment_id)
        if c2.button(t("history.run_again"), width="stretch", disabled=active is not None,
                     help=t("history.run_again_help")):
            ids = [c["id"] for c in e.carriers if c.get("selected", True)]
            wr.start(ROOT, e.to_dict(), ids)
            open_in_workspace(experiment=e.experiment_id)
        with c3.popover(t("history.rename_or_copy"), width="stretch"):
            name = st.text_input(t("workspace.experiment.name"), value=e.name, key=f"h_name_{e.experiment_id}")
            if st.button(t("workspace.experiment.rename_button"), width="stretch"):
                xp.rename(ROOT, e.experiment_id, name)
                st.rerun()
            if st.button(t("workspace.experiment.duplicate_button"), width="stretch"):
                xp.duplicate(ROOT, e.experiment_id, name if name != e.name else
                             t("workspace.experiment.copy_of", name=e.name))
                st.rerun()
        if c4.button(t("workspace.experiment.delete"), width="stretch"):
            confirm_delete(e)
        runs = xp.runs_of(ROOT, e.experiment_id)
        st.caption(t("history.experiment_runs", runs=", ".join(runs) if runs else t("common.none")))

# ---------------------------------------------------------------- completed runs
st.subheader(t("history.runs"))
st.caption(t("history.runs_caption"))
all_runs = [ui.run(p) for p in ui.run_list()]
if not all_runs:
    st.caption(t("common.none_yet"))
else:
    names = {e.experiment_id: e.name for e in experiments}
    rows = []
    for r in all_runs:
        m = r.manifest
        exp_ = m.get("experiment") or {}
        rows.append({t("history.columns.created"): when(m.get("created_utc", "")),
                     t("history.columns.source"): t("history.sources.workspace") if r.is_workspace else
                     t(f"history.sources.{r.kind}"),
                     t("history.columns.experiment"): names.get(exp_.get("id"), exp_.get("name") or "—"),
                     t("history.columns.dataset"): f"{m['area']['name']}/{m['area'].get('variant', '')}",
                     t("history.columns.carriers"): ", ".join(f"{s['frequency_hz'] / 1e9:g}" for s in r.scenarios) + " GHz",
                     t("history.columns.stations"): len(r.sites),
                     t("history.columns.class"): head(r) + (f" · {t('common.invalid_prefix')}" if r.invalid else ""),
                     t("history.columns.profile"): f"{m['profile']['name']} · {r.backend.upper()}",
                     t("history.columns.duration"): ui.fmt((m.get("timing") or {}).get("total_wall_seconds"), ".0f", " s")})
    picked = st.dataframe(rows, hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row",
                          key="h_runs")
    chosen = list(picked.selection.rows) if picked is not None else []
    if not chosen:
        st.caption(t("history.pick_run"))
    else:
        r = all_runs[chosen[0]]
        c1, c2, c3, c4 = st.columns(4)
        if c1.button(t("history.view"), type="primary", width="stretch", disabled=r.kind == "site_plan"):
            SS["coverage-run"] = str(r.path)
            st.switch_page("views/coverage.py")
        if c2.button(t("history.open_run"), width="stretch", disabled=r.kind not in ("multi_site", "site_plan"),
                     help=t("history.open_run_help")):
            open_in_workspace(run=str(r.path))
        if c3.button(t("history.report"), width="stretch"):
            SS["report-run"] = str(r.path)
            st.switch_page("views/reports.py")
        if c4.button(t("history.compare", n=len(chosen)), width="stretch", disabled=len(chosen) < 2,
                     help=t("history.compare_help")):
            SS["cmp-runs"] = [str(all_runs[i].path) for i in chosen]
            st.switch_page("views/comparison.py")

# ---------------------------------------------------------------- background simulations
st.subheader(t("history.processes"))
st.caption(t("history.processes_caption"))
items = [("workspace", f) for f in wr.history(ROOT)[:8]] + [("script", f) for f in control.history(ROOT)[:5]]
if not items:
    st.caption(t("common.none_yet"))


def show(kind, folder) -> None:
    if kind == "workspace":
        s = wr.state(folder)
        title = (s.request.get("experiment") or {}).get("name") or folder.name
        detail = t("history.trace_line", done=s.committed, total=s.total, retries=s.retries,
                   s=f"{s.elapsed_seconds:.0f}")
        output = s.output
    else:
        s = control.state(folder)
        req = s.request
        title = f"{req.get('area')}/{req.get('variant')} · {req.get('profile')}"
        detail = t("simulation.history.traced", done=s.progress[0], total=s.progress[1]) if s.progress else ""
        output = s.output
    with st.container(border=True):
        st.markdown(f"**{t('history.execution.' + s.execution.lower())}** · {title} · "
                    f"{t('simulation.history.started', date=when(s.request.get('started_utc', '')))}"
                    + (f" · {detail}" if detail else ""))
        if s.running:
            if st.button(t("simulation.history.cancel"), key=f"h-cancel-{folder.name}"):
                (wr.cancel if kind == "workspace" else control.cancel)(folder)
                st.toast(t("simulation.history.cancelling"))
        elif output:
            st.caption(t("history.output", run=ui.ltr(output.name)), unsafe_allow_html=True)
        elif getattr(s, "error", None):
            st.error(s.error)
        with st.expander(t("simulation.history.log")):
            st.code("\n".join(s.log_tail) or "(empty)", language="text")


live = st.fragment(run_every=3)(show)
for kind, folder in items:
    try:
        running = (wr.state(folder) if kind == "workspace" else control.state(folder)).running
    except (OSError, ValueError, KeyError):
        continue
    (live if running else show)(kind, folder)
