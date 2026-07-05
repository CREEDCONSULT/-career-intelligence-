"""Shared rendering helpers for dashboard pages."""
import csv
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

BRAND = {
    "growth": "#0FA958",
    "wealth": "#D4A80D",
    "clarity": "#0A72EF",
    "signal": "#7A4DFF",
    "ink": "#273951",
}

_BADGE_CLASS = {"High": "confidence-high", "Medium": "confidence-medium", "Low": "confidence-low"}


def confidence_badge(level: str) -> str:
    return f'<span class="confidence-badge {_BADGE_CLASS.get(level, "confidence-high")}">{level} Confidence</span>'


def data_meta(level: str, source_text: str) -> None:
    st.markdown(
        f'<div class="data-meta">{confidence_badge(level)}<span>{source_text}</span></div>',
        unsafe_allow_html=True,
    )


def methodology(markdown_text: str) -> None:
    with st.expander("📋 Methodology", expanded=False):
        st.markdown(markdown_text)


def money_safe(text: str) -> str:
    """Escape ``$`` so Streamlit doesn't render '$20-$30' as LaTeX math."""
    return (text or "").replace("$", "\\$")


# --- Lead capture -----------------------------------------------------------
# In-app form captures name + email (no mail client needed). Submissions are
# relayed to the owner via a form endpoint and backed up to a local CSV.
#   LEAD_WEBHOOK_URL  — a form-relay endpoint (Formspree/Web3Forms/Google Apps
#                       Script/etc.) that receives JSON {name,email,interest}.
#   CONTACT_EMAIL     — if no webhook is set, defaults to FormSubmit's free,
#                       no-account relay: https://formsubmit.co/ajax/<email>
#                       (owner clicks a one-time activation email to start).

_LEADS_CSV = Path(__file__).resolve().parents[2] / "data" / "processed" / "leads.csv"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _lead_webhook() -> str:
    url = os.getenv("LEAD_WEBHOOK_URL", "").strip()
    if url:
        return url
    email = os.getenv("CONTACT_EMAIL", "").strip()
    return f"https://formsubmit.co/ajax/{email}" if email else ""


def _save_lead_local(name: str, email: str, interest: str) -> None:
    try:
        _LEADS_CSV.parent.mkdir(parents=True, exist_ok=True)
        new = not _LEADS_CSV.exists()
        with open(_LEADS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp_utc", "name", "email", "interest"])
            w.writerow([datetime.utcnow().isoformat(timespec="seconds"), name, email, interest])
    except Exception:  # noqa: BLE001 - backup is best-effort
        pass


def _relay_lead(name: str, email: str, interest: str) -> bool:
    hook = _lead_webhook()
    if not hook:
        return False
    payload = {
        "name": name, "email": email, "interest": interest,
        "_subject": f"[Career Intelligence] New lead — {interest}",
        "_captcha": "false", "_template": "table",
    }
    try:
        import requests
        r = requests.post(hook, json=payload, timeout=12,
                          headers={"Accept": "application/json"})
        return r.ok
    except Exception:  # noqa: BLE001 - never break the UI on a network hiccup
        return False


def lead_form(context: str = "sidebar", compact: bool = True) -> None:
    """Render a name + email capture form. Works without a mail client."""
    st.markdown("**📬 Stay in the loop**" if compact else "### 📬 Stay in the loop")
    with st.form(f"lead_{context}", clear_on_submit=True):
        name = st.text_input("Name", placeholder="Your name", label_visibility="collapsed" if compact else "visible")
        email = st.text_input("Email", placeholder="you@email.com", label_visibility="collapsed" if compact else "visible")
        interest = st.selectbox(
            "I'm interested in",
            ["Monthly market brief", "Beta waitlist", "For teams / schools"],
            label_visibility="collapsed" if compact else "visible",
        )
        submitted = st.form_submit_button("Notify me →", use_container_width=True)
    if not submitted:
        return
    if not _EMAIL_RE.match((email or "").strip()):
        st.warning("Please enter a valid email.")
        return
    name, email = (name or "").strip() or "—", email.strip()
    _save_lead_local(name, email, interest)
    _relay_lead(name, email, interest)
    st.success("You're on the list — thanks! 🎉")


def style_fig(fig, accent: str = "ink"):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Source Sans 3",
        font_color="#273951",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E5EDF5")
    return fig
