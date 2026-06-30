"""Page: Market Context."""
import plotly.express as px
import streamlit as st

from pipeline.insights import get_market_context

from ._shared import BRAND, data_meta, methodology, style_fig

METHODOLOGY = """
**Data Sources:**
- **Toronto hiring momentum** — Indeed Hiring Lab metro postings index (Toronto, ON), base Feb 2020 = 100.
- **Toronto vacancies & offered wages** — Statistics Canada Job Vacancies (Table 14-10-0444-01), Toronto economic region, quarterly.
- **Posted wage growth (Canada)** — Indeed Hiring Lab, year-over-year.
- **AI share of postings (Canada)** — Indeed Hiring Lab AI tracker.

**Confidence:** High — all official Indeed Hiring Lab / Statistics Canada series.
"""


def render(date_range: str = "Last 12 months") -> None:
    st.header("Market Context")
    st.caption("Macro hiring momentum, vacancies, wage growth, and AI demand")
    data_meta("High", "Source: Indeed Hiring Lab + Statistics Canada JVWS")
    methodology(METHODOLOGY)

    ctx = get_market_context()
    postings = ctx["postings_index"]
    wage = ctx["wage_growth"]
    ai = ctx["ai_share"]
    vac = ctx["vacancy_trends"]

    if postings.empty and vac.empty and ai.empty:
        st.warning("No market data. Run the downloaders + `python scripts/transform.py`.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Toronto hiring momentum")
        if not postings.empty:
            fig = px.area(postings, x="date", y="value")
            fig.update_traces(line_color=BRAND["signal"], fillcolor="rgba(122,77,255,0.12)")
            fig.update_layout(xaxis_title="", yaxis_title="Index (Feb 2020 = 100)")
            st.plotly_chart(style_fig(fig, "signal"), use_container_width=True)
        else:
            st.info("No Indeed metro data.")
    with c2:
        st.subheader("AI share of postings (Canada)")
        if not ai.empty:
            fig = px.line(ai, x="date", y="value")
            fig.update_traces(line_color=BRAND["clarity"])
            fig.update_layout(xaxis_title="", yaxis_title="% of postings")
            st.plotly_chart(style_fig(fig, "clarity"), use_container_width=True)
        else:
            st.info("No AI tracker data.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Toronto vacancies (quarterly)")
        if not vac.empty:
            vac = vac.copy()
            vac["period"] = vac["year"].astype(int).astype(str) + "-Q" + vac["quarter"].astype(int).astype(str)
            fig = px.bar(vac, x="period", y="total_vacancies")
            fig.update_traces(marker_color=BRAND["growth"])
            fig.update_layout(xaxis_title="", yaxis_title="Job vacancies")
            st.plotly_chart(style_fig(fig, "growth"), use_container_width=True)
        else:
            st.info("StatsCan vacancy data not loaded (run from a Canadian connection).")
    with c4:
        st.subheader("Posted wage growth (Canada, YoY)")
        if not wage.empty:
            fig = px.line(wage, x="date", y="value")
            fig.update_traces(line_color=BRAND["wealth"])
            fig.update_layout(xaxis_title="", yaxis_title="YoY wage growth")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(style_fig(fig, "wealth"), use_container_width=True)
        else:
            st.info("No wage-growth data.")
