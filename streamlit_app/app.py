"""
Career Intelligence Dashboard - Streamlit app (router).

Each insight view lives in streamlit_app/pages_impl/<page>.py as a render() fn.
"""
import streamlit as st

from pages_impl import market_context, role_fit, salary_ranges, skill_demand

st.set_page_config(
    page_title="Career Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root {
    --brand-primary: #3B2F9E; --accent-growth: #0FA958; --accent-wealth: #D4A80D;
    --accent-clarity: #0A72EF; --accent-signal: #7A4DFF;
}
.stApp { background-color: #F7F9FC; font-family: 'Source Sans 3', system-ui, sans-serif; }
h1, h2, h3, h4 { font-family: 'Source Sans 3', system-ui, sans-serif; color: #061B31; font-weight: 300; line-height: 1.1; }
h1 { font-size: 2.5rem; letter-spacing: -0.02em; }
h2 { font-size: 1.625rem; letter-spacing: -0.01em; }
h3 { font-size: 1.375rem; letter-spacing: -0.01em; }
.stButton > button { background-color: #3B2F9E !important; color: white !important; border: none !important; border-radius: 4px !important; padding: 12px 20px !important; font-weight: 400 !important; }
.stButton > button:hover { background-color: #4A3FC0 !important; }
.data-meta { display: flex; gap: 16px; font-size: 0.75rem; color: #64748D; align-items: center; margin-bottom: 8px; }
.confidence-badge { display: inline-flex; padding: 2px 8px; border-radius: 9999px; font-size: 0.625rem; font-weight: 600; font-family: 'Geist Mono', monospace; text-transform: uppercase; }
.confidence-high { background: rgba(21,190,83,0.15); color: #108C3D; border: 1px solid rgba(21,190,83,0.3); }
.confidence-medium { background: rgba(212,168,13,0.15); color: #9B6829; border: 1px solid #D4A80D; }
.confidence-low { background: rgba(234,34,97,0.15); color: #C41A4D; border: 1px solid #EA2261; }
#MainMenu { visibility: hidden; } footer { visibility: hidden; } header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

PAGES = {
    "📈 Skill Demand": skill_demand,
    "💰 Salary Ranges": salary_ranges,
    "🎯 Role Fit": role_fit,
    "📊 Market Context": market_context,
}

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:1rem 0;'>"
        "<h1 style='font-size:1.5rem;margin-bottom:0;'>Career Intelligence</h1>"
        "<p style='color:#64748D;font-size:0.875rem;'>Toronto job market, decoded.</p></div>",
        unsafe_allow_html=True,
    )
    page = st.radio("Insights", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.markdown("**Filters**")
    date_range = st.selectbox(
        "Time Period",
        ["Last 12 months", "Last 6 months", "Last 3 months", "Year to Date"],
        index=0,
    )
    st.divider()
    st.markdown("**Data Freshness**")
    for src, dt in {
        "Job Bank Postings": "monthly",
        "Job Bank Wages": "2025",
        "StatsCan JVWS": "Q1 2026",
        "Indeed Trends": "monthly",
    }.items():
        st.caption(f"{src}: {dt}")
    st.divider()
    st.caption("Built by Dante (Mr. C. Mezie) · creedConsult")

st.title("Career Intelligence Dashboard")
st.caption("Transforming Toronto job postings into actionable career intelligence")

PAGES[page].render(date_range)
