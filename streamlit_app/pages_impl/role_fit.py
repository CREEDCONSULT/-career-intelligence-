"""Page: Role Fit Signal."""
import plotly.graph_objects as go
import streamlit as st

from pipeline.insights import compute_role_fit, get_skill_demand_trends

from ._shared import BRAND, data_meta, methodology

METHODOLOGY = """
**How it works:** We take the top ~50 most-demanded skills in recent Toronto postings, match your
entered skills against the same Lightcast taxonomy + synonym index used for extraction, and compute
the share of demanded skills you already cover.

**Confidence:** Medium — fit depends on the skills you enter and on title-based demand extraction
(see Skill Demand methodology). Use it directionally, not as a precise score.
"""


def render(date_range: str = "Last 12 months") -> None:
    st.header("Role Fit Signal")
    st.caption("Match your skills against current Toronto demand and find your gaps")
    data_meta("Medium", "Source: Toronto skill demand + Lightcast taxonomy · user-dependent")
    methodology(METHODOLOGY)

    trends = get_skill_demand_trends()
    if trends.empty:
        st.warning("No demand data. Run `python scripts/transform.py` to load data.")
        return

    skill_options = sorted(trends["skill_name"].dropna().unique().tolist())
    picked = st.multiselect(
        "Your skills", options=skill_options,
        default=skill_options[:3] if len(skill_options) >= 3 else skill_options,
        help="Start typing to search the skills seen in Toronto postings.",
    )
    extra = st.text_input("Add skills not listed (comma-separated)", "")
    user_skills = list(picked) + [s.strip() for s in extra.split(",") if s.strip()]

    if not user_skills:
        st.info("Select or type at least one skill to compute your fit.")
        return

    result = compute_role_fit(user_skills)
    if "error" in result:
        st.warning(result["error"])
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=result["fit_score"],
            number={"suffix": "%"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": BRAND["clarity"]},
                   "steps": [{"range": [0, 33], "color": "#E8F0FE"},
                             {"range": [33, 66], "color": "#CFE2FD"},
                             {"range": [66, 100], "color": "#A9CCFB"}]},
            title={"text": "Market Fit"},
        ))
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", font_color="#273951")
        st.plotly_chart(fig, use_container_width=True)
        st.success(result["recommendation"])
    with col2:
        st.subheader("Top skill gaps in Toronto")
        gaps = result.get("gap_skills", [])
        if gaps:
            import pandas as pd
            gdf = pd.DataFrame(gaps)[["skill_name", "category", "demand_cnt"]].rename(
                columns={"skill_name": "Skill", "category": "Category", "demand_cnt": "Postings"})
            st.dataframe(gdf, hide_index=True, use_container_width=True, height=320)
        else:
            st.info("No gaps — your skills cover the top demanded set.")
        matched = result.get("matched_skills", [])
        if matched:
            st.caption("✅ You match: " + ", ".join(m["skill_name"] for m in matched[:12]))
