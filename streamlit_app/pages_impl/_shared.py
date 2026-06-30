"""Shared rendering helpers for dashboard pages."""
import plotly.express as px
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
