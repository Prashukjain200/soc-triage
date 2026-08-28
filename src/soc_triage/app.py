"""Streamlit UI: upload alerts.csv, then triage every pending alert with the
supervisor agent, pausing in the UI whenever it wants to dismiss an alert and
needs human approval first.

    streamlit run src/soc_triage/app.py
"""
# pyrefly: ignore [missing-import]
import pandas as pd
import streamlit as st

from soc_triage import config
from soc_triage.agents import supervisor_agent
from soc_triage.pipeline import load_pending_alerts, run_alert, resume_alert

st.set_page_config(page_title="Security Alert Triage", page_icon="🛡️", layout="wide")

REQUIRED_COLUMNS = [
    "alert_id", "user_email", "timestamp", "ip", "event_type",
    "mfa_used", "resource_accessed", "raw_description", "status",
]

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600&family=Inter:wght@400;500;600&family=Material+Symbols+Outlined&display=swap');

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

    .material-symbols-outlined { font-family: 'Material Symbols Outlined'; font-size: 1.7rem; vertical-align: middle; }

    .hero { padding: 0.25rem 0 1.1rem; border-bottom: 1px solid rgba(61,214,200,0.18); margin-bottom: 1.3rem; display:flex; align-items:center; gap:0.6rem; }
    .hero h1 { margin: 0; font-size: 1.9rem; color: #3DD6C8; letter-spacing: -0.01em; }
    .hero .material-symbols-outlined { color: #3DD6C8; }
    .hero-sub { margin: 0.15rem 0 0; color: #8B98A5; font-size: 0.93rem; }

    .mono { font-family: 'JetBrains Mono', monospace; }

    .alert-card {
        background: #111823;
        border: 1px solid rgba(61,214,200,0.28);
        border-radius: 12px;
        padding: 1.1rem 1.35rem;
        margin: 0.75rem 0 1rem;
    }
    .alert-card .field { margin: 0.2rem 0; font-size: 0.93rem; color: #C6D0DA; }
    .alert-card .field b { color: #E6EDF3; }

    .log-row {
        background: #111823;
        border-left: 3px solid #3DD6C8;
        border-radius: 6px;
        padding: 0.55rem 0.9rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        color: #C6D0DA;
    }
    .log-row .aid { font-family: 'JetBrains Mono', monospace; color: #3DD6C8; margin-right: 0.6rem; font-weight: 600; }

    .badge { display: inline-block; padding: 0.12rem 0.6rem; border-radius: 999px; font-size: 0.74rem; font-weight: 600; margin-left: 0.5rem; }
    .badge-yes { background: rgba(61,214,200,0.16); color: #3DD6C8; }
    .badge-no { background: rgba(240,90,90,0.16); color: #F05A5A; }
    .badge-escalated { background: rgba(240,90,90,0.16); color: #F05A5A; }
    .badge-dismissed { background: rgba(61,214,200,0.16); color: #3DD6C8; }
    .badge-review { background: rgba(240,190,90,0.16); color: #F0BE5A; }

    .empty-state { text-align: center; padding: 3rem 1rem; color: #6B7684; }
    .empty-state .material-symbols-outlined { font-size: 2.6rem; color: #3DD6C8; opacity: 0.6; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><span class="material-symbols-outlined">shield</span>'
    '<div><h1>Security Alert Triage</h1>'
    '<p class="hero-sub">Multi-agent investigation of pending alerts, with a human gate on every dismissal.</p></div>'
    '</div>',
    unsafe_allow_html=True,
)

if "queue" not in st.session_state:
    st.session_state.queue = None
    st.session_state.awaiting = None
    st.session_state.log = []
    st.session_state.supervisor = None


def classify_outcome(summary: str) -> tuple[str, str]:
    """Best-effort label for a processed alert, parsed from the agent's closing
    summary text (the structured status lives in alerts.csv via resolve_alert,
    but isn't threaded back through the graph result — this is a display hint,
    not an authoritative status)."""
    lowered = summary.lower()
    if "escalat" in lowered:
        return "Escalated", "badge-escalated"
    if "dismiss" in lowered:
        return "Dismissed", "badge-dismissed"
    return "Reviewed", "badge-review"


def handle_result(row, result):
    if "__interrupt__" in result:
        interrupt = result["__interrupt__"][0]
        st.session_state.awaiting = {"row": row, "interrupt": interrupt.value}
    else:
        st.session_state.log.append((row["alert_id"], result["messages"][-1].content))


def validate_alerts_csv(path):
    """Check the alerts CSV has the columns the pipeline and tools rely on,
    so a bad upload fails with a clear message instead of a KeyError deep
    inside an agent tool call."""
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return f"Could not read this CSV: {e}"
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return f"Missing required column(s): {', '.join(missing)}"
    return None


with st.sidebar:
    st.markdown("### Queue")
    uploaded = st.file_uploader("Upload alerts.csv", type="csv")
    if uploaded is not None:
        config.ALERTS_CSV.write_bytes(uploaded.getvalue())
        st.success(f"Saved to {config.ALERTS_CSV.name}")

    if st.button("Use demo data", icon=":material/science:", use_container_width=True):
        config.ALERTS_CSV.write_bytes(config.SAMPLE_ALERTS_CSV.read_bytes())
        st.session_state.queue = None
        st.session_state.awaiting = None
        st.session_state.log = []
        st.success("Loaded the sample alerts.csv bundled with this app")
        st.rerun()

    csv_error = validate_alerts_csv(config.ALERTS_CSV) if config.ALERTS_CSV.exists() else None
    if csv_error:
        st.error(csv_error)

    start_disabled = (not config.ALERTS_CSV.exists()) or bool(csv_error)
    if st.button("Run queue", type="primary", icon=":material/play_arrow:", disabled=start_disabled, use_container_width=True):
        st.session_state.supervisor = supervisor_agent()
        st.session_state.queue = list(load_pending_alerts().to_dict("records"))
        st.session_state.awaiting = None
        st.session_state.log = []
        st.rerun()

    with st.expander("Getting started / required inputs"):
        st.markdown(
            "**alerts.csv columns**\n"
            f"`{'`, `'.join(REQUIRED_COLUMNS)}`\n\n"
            "**Environment variables** (in `.env`)\n"
            "- `OPENAI_API_KEY` — required, powers every agent\n"
            "- `SERPER_API_KEY` — for internet IP lookups\n"
            "- `PUSHOVER_TOKEN` / `PUSHOVER_USER` — for admin push notifications\n\n"
            "Reference data (`data/users.csv`, `data/ip_reputation.csv`, "
            "`data/security_triage_policy.md`) ships with the repo — only "
            "`alerts.csv` needs uploading."
        )

if st.session_state.queue is None:
    if config.ALERTS_CSV.exists() and not csv_error:
        preview_df = pd.read_csv(config.ALERTS_CSV)
        pending_count = int((preview_df["status"] == "pending").sum())
        with st.expander(f"Preview — {len(preview_df)} row(s), {pending_count} pending", expanded=True):
            st.dataframe(preview_df, use_container_width=True, height=260)
    else:
        st.markdown(
            '<div class="empty-state">'
            '<div class="material-symbols-outlined">upload_file</div>'
            '<p>Upload an alerts.csv in the sidebar, or click "Use demo data" to try it instantly.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

total_processed = len(st.session_state.log)
pending_left = len(st.session_state.queue) if st.session_state.queue is not None else 0
total_this_run = pending_left + total_processed

m1, m2, m3 = st.columns(3)
m1.metric("Pending", pending_left)
m2.metric("Processed", total_processed)
m3.metric("Awaiting approval", 1 if st.session_state.awaiting else 0)

if st.session_state.queue is not None and total_this_run > 0:
    st.progress(total_processed / total_this_run)

# Process exactly one alert per rerun, so the UI updates incrementally
# instead of freezing for the entire queue's worth of agent calls.
if st.session_state.queue and st.session_state.awaiting is None:
    row = st.session_state.queue.pop(0)
    with st.spinner(f"Investigating {row['alert_id']} — {total_processed + 1} of {total_this_run}…"):
        result = run_alert(st.session_state.supervisor, row)
    handle_result(row, result)
    st.rerun()

awaiting = st.session_state.awaiting
if awaiting is not None:
    row = awaiting["row"]
    st.warning(f"Alert **{row['alert_id']}** wants to dismiss — needs human approval")

    mfa_raw = str(row.get("mfa_used", "")).strip()
    mfa_class = "badge-yes" if mfa_raw.lower().startswith("yes") else "badge-no"
    st.markdown(
        f'<div class="alert-card">'
        f'<div class="field"><b>User</b> · {row["user_email"]}</div>'
        f'<div class="field"><b>IP</b> · <span class="mono">{row["ip"]}</span>'
        f'<span class="badge {mfa_class}">MFA: {mfa_raw or "unknown"}</span></div>'
        f'<div class="field"><b>Event</b> · {row.get("event_type", "—")}</div>'
        f'<div class="field"><b>Resource</b> · {row["resource_accessed"]}</div>'
        f'<div class="field"><b>Description</b> · {row["raw_description"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Agent's proposed resolution"):
        st.json(awaiting["interrupt"])

    approve_col, deny_col = st.columns(2)
    if approve_col.button("Approve dismissal", icon=":material/check_circle:", use_container_width=True):
        result = resume_alert(st.session_state.supervisor, row["alert_id"], approved=True)
        st.session_state.awaiting = None
        handle_result(row, result)
        st.rerun()
    if deny_col.button("Reject — keep escalated", icon=":material/cancel:", use_container_width=True):
        result = resume_alert(st.session_state.supervisor, row["alert_id"], approved=False)
        st.session_state.awaiting = None
        handle_result(row, result)
        st.rerun()

if st.session_state.log:
    st.markdown("#### Processed this run")
    for alert_id, summary in reversed(st.session_state.log):
        label, badge_class = classify_outcome(summary)
        with st.expander(f"{alert_id} — {label}", expanded=False):
            st.markdown(f'<span class="badge {badge_class}">{label}</span>', unsafe_allow_html=True)
            st.write(summary)

    st.download_button(
        "Download alerts.csv (with resolutions)",
        data=config.ALERTS_CSV.read_bytes(),
        file_name="alerts_resolved.csv",
        mime="text/csv",
        icon=":material/download:",
    )

if st.session_state.queue == [] and st.session_state.awaiting is None and st.session_state.log:
    st.success("Queue complete.")
