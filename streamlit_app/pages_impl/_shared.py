"""Shared rendering helpers for dashboard pages."""
import os
from urllib.parse import quote

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
# All destinations are env-configurable. Set any of these to activate the CTAs:
#   BRIEF_SIGNUP_URL   — newsletter/form for the monthly Market Brief
#   WAITLIST_URL       — beta waitlist form
#   PILOT_BOOKING_URL  — booking/form for teams, coaches, schools
#   CONTACT_EMAIL      — universal fallback: CTAs become pre-filled mailto links

def _lead_targets():
    return {
        "brief": os.getenv("BRIEF_SIGNUP_URL", "").strip(),
        "waitlist": os.getenv("WAITLIST_URL", "").strip(),
        "pilot": os.getenv("PILOT_BOOKING_URL", "").strip(),
        "email": os.getenv("CONTACT_EMAIL", "").strip(),
    }


def _cta_url(direct: str, email: str, subject: str) -> str | None:
    if direct:
        return direct
    if email:
        return f"mailto:{email}?subject={quote(subject)}"
    return None


def lead_ctas(compact: bool = True) -> None:
    """Render the lead-capture CTAs (brief · waitlist · teams/schools).

    Renders only the CTAs that are configured (dedicated URL or mailto fallback).
    If nothing is configured, shows a quiet, public-safe placeholder line.
    """
    t = _lead_targets()
    brief = _cta_url(t["brief"], t["email"], "Subscribe — monthly Toronto job market brief")
    waitlist = _cta_url(t["waitlist"], t["email"], "Join the beta waitlist")
    pilot = _cta_url(t["pilot"], t["email"], "Pilot inquiry — teams, coaches & schools")

    st.markdown("**📬 Stay in the loop**" if compact else "### 📬 Stay in the loop")
    if not any([brief, waitlist, pilot]):
        st.caption("Subscribe & pilot options coming soon.")
        return
    if brief:
        st.link_button("📩 Monthly market brief", brief, use_container_width=True)
    if waitlist:
        st.link_button("🔔 Join the beta waitlist", waitlist, use_container_width=True)
    if pilot:
        st.link_button("🏫 For teams & schools", pilot, use_container_width=True)


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
