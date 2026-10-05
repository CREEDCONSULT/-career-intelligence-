"""Page: Salary Ranges by Role."""
import plotly.graph_objects as go
import streamlit as st

from pipeline.insights import get_salary_by_role

from ._shared import BRAND, data_meta, methodology, style_fig

METHODOLOGY = """
**Data Sources:** Job Bank Wages (open.canada.ca, Toronto economic region ER3530) joined with
Statistics Canada Job Vacancies (Table 14-10-0444-01) on NOC 2021 code.

**Normalization:** Annual wage figures are converted to an hourly equivalent (÷ 2,080 hrs/yr) so all
roles are comparable. Roles are filtered to those with a meaningful vacancy count in Toronto.

**Confidence:** High — official government wage and vacancy data.
"""


def render(date_range: str = "Last 12 months") -> None:
    st.header("Salary Ranges by Role")
    st.caption("Hourly-equivalent compensation for Toronto occupations, vacancy-weighted")
    data_meta("High", "Source: Job Bank Wages (ER3530) + StatsCan JVWS · NOC 2021")
    methodology(METHODOLOGY)

    df = get_salary_by_role(min_vacancies=1)
    if df.empty:
        st.warning("No salary data. Run `python scripts/transform.py` to load data.")
        return

    df = df.sort_values("total_vacancies", ascending=False)

    # KPI row
    c1, c2, c3 = st.columns(3)
    c1.metric("Roles covered", f"{len(df):,}")
    c2.metric("Median wage (all roles)", f"${df['median_wage'].median():.2f}/hr")
    c3.metric("Top role by vacancies", df.iloc[0]["role_title"][:28])

    # Searchable lookup
    st.subheader("Look up a role")
    role = st.selectbox("Occupation", df["role_title"].tolist(), index=0)
    r = df[df["role_title"] == role].iloc[0]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Low", f"${r['min_wage']:.2f}/hr")
    k2.metric("Median", f"${r['median_wage']:.2f}/hr")
    k3.metric("High", f"${r['max_wage']:.2f}/hr")
    k4.metric("Vacancies", f"{int(r['total_vacancies']):,}")

    # Range plot for the top roles by vacancy count
    st.subheader("Wage ranges — top roles by vacancy volume")
    top = df.head(15).iloc[::-1]
    fig = go.Figure()
    for _, row in top.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["min_wage"], row["max_wage"]], y=[row["role_title"], row["role_title"]],
            mode="lines", line=dict(color="#E5EDF5", width=6), showlegend=False, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=top["median_wage"], y=top["role_title"], mode="markers",
        marker=dict(color=BRAND["wealth"], size=11, line=dict(color="white", width=1)),
        name="Median", hovertemplate="%{y}<br>Median $%{x:.2f}/hr<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Hourly wage (CAD)", yaxis_title="", height=520, showlegend=False)
    st.plotly_chart(style_fig(fig, "wealth"), use_container_width=True)
