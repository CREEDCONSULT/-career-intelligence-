"""Page: Skill Demand Trends."""
import plotly.express as px
import streamlit as st

from pipeline.insights import get_emerging_skills, get_skill_demand_trends

from ._shared import BRAND, data_meta, methodology, style_fig

METHODOLOGY = """
**Data Source:** Job Bank Open Data monthly CSVs (open.canada.ca), filtered for Toronto/GTA municipalities.

**Skill Extraction:** Single-pass phrase matching (flashtext) against the Lightcast Open Skills
taxonomy (~33K skills) plus a curated tech/ops synonym map.

**Important limitation:** Job Bank postings contain **no job-requirements free text**. Skills are
extracted from the job **title** + NOC occupation name. This surfaces role/function-level demand
(e.g. Sales, Marketing, IT) well, but under-counts tools named only in body text (e.g. a specific
library). Treat this as occupational demand, not a full skills census.

**Processing:** Monthly aggregation of distinct postings mentioning each skill.
"""


def render(date_range: str = "Last 12 months") -> None:
    st.header("Skill Demand Trends")
    st.caption("Top skills in Toronto job postings, monthly trends, and emerging skills")
    data_meta("High", "Source: Job Bank Open Data (Toronto postings) · title-based extraction")
    methodology(METHODOLOGY)

    trends = get_skill_demand_trends()
    emerging = get_emerging_skills()

    if trends.empty:
        st.warning("No skill demand data. Run `python scripts/transform.py` to load data.")
        return

    latest = trends["month"].max()
    current = trends[trends["month"] == latest].head(20)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"Top Skills — {latest.strftime('%B %Y')}")
        st.dataframe(
            current[["rank", "skill_name", "category", "postings_count"]].rename(
                columns={"rank": "Rank", "skill_name": "Skill", "category": "Category", "postings_count": "Postings"}
            ),
            hide_index=True, use_container_width=True, height=460,
        )
    with col2:
        st.subheader("🚀 Emerging Skills")
        if not emerging.empty:
            for _, row in emerging.head(10).iterrows():
                st.markdown(
                    f"<div style='padding:8px;background:#E6F7EB;border-radius:4px;margin:4px 0;'>"
                    f"<strong>{row['skill_name']}</strong><br>"
                    f"<small>+{row['qoq_growth']*100:.0f}% MoM · {int(row['current_cnt'])} postings</small></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No emerging skills detected this period.")

    st.subheader("Monthly Trend — Top 10 Skills")
    top10 = current.head(10)["skill_name"].tolist()
    subset = trends[trends["skill_name"].isin(top10)]
    fig = px.line(subset, x="month", y="postings_count", color="skill_name",
                  color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(xaxis_title="Month", yaxis_title="Postings")
    st.plotly_chart(style_fig(fig, "growth"), use_container_width=True)
