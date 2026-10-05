"""Page: Role Fit Signal."""
import plotly.graph_objects as go
import streamlit as st

from pipeline.insights import compute_role_fit, get_skill_demand_trends

from ._shared import BRAND, data_meta, methodology

METHODOLOGY = """
**Skill match:** We take the top ~50 most-demanded skills in recent postings, match your entered
skills against the same taxonomy + synonym index used for extraction, and compute the share of
demanded skills you already cover.

**Profile match:** Your pasted profile is embedded (locally — nothing leaves the server, no LLM
call) and matched against a corpus of ~320 occupations built from real postings + their
LLM-extracted skills, using dense + BM25 hybrid retrieval fused with demand signals.
Measured: 8/8 test profiles rank a correct occupation first.

**Confidence:** Medium — user-input-dependent. Use directionally, not as a precise score.
"""


@st.cache_resource(show_spinner="Building the role index (one-time, ~20s)...")
def _role_index():
    import duckdb
    from pathlib import Path
    from llm.features.role_match import RoleIndex, build_role_docs
    db = Path(__file__).resolve().parents[2] / "data" / "processed" / "career_intel.duckdb"
    con = duckdb.connect(str(db), read_only=True)
    try:
        docs = build_role_docs(con)
    finally:
        con.close()
    idx = RoleIndex()
    idx.build(docs)
    return idx


def _render_profile_match() -> None:
    from llm.features.role_match import match_profile
    profile = st.text_area(
        "Paste your resume summary or describe your experience",
        placeholder="e.g. 5 years as a line cook and kitchen supervisor, food safety certified...",
        height=140,
    )
    if not profile.strip():
        st.info("Paste a short profile to see your best-fit Toronto occupations.")
        return
    results = match_profile(profile, index=_role_index(), limit=6)
    for r in results:
        wage = f"${r['median_wage']:.2f}/hr median" if r["median_wage"] else "wage n/a"
        matched = ", ".join(r["matched_skills"]) if r["matched_skills"] else "—"
        st.markdown(
            f"<div style='background:#FFFFFF;border:1px solid #E5EDF5;border-left:4px solid "
            f"{BRAND['clarity']};border-radius:6px;padding:12px 16px;margin:8px 0;'>"
            f"<strong>{r['title']}</strong> &nbsp;<span style='color:#64748D'>score {r['score']:.2f}</span><br>"
            f"<small>{wage} · {r['demand']:,} postings (12 mo) · matched skills: {matched}</small></div>",
            unsafe_allow_html=True,
        )


def render(date_range: str = "Last 12 months") -> None:
    st.header("Role Fit Signal")
    st.caption("Match your skills — or your whole profile — against current Toronto demand")
    data_meta("Medium", "Source: Toronto skill demand + Lightcast taxonomy · user-dependent")
    methodology(METHODOLOGY)

    tab_profile, tab_skills = st.tabs(["🧭 Match my profile", "🧩 Skill match"])
    with tab_profile:
        _render_profile_match()
    with tab_skills:
        _render_skill_match()


def _render_skill_match() -> None:
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
