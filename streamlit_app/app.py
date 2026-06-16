"""
Career Intelligence Dashboard - Streamlit App
"""
import streamlit as st
import yaml
import re
from pathlib import Path

st.set_page_config(page_title="Career Intelligence Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

@st.cache_data
def load_design_tokens():
    with open("brand/DESIGN.md") as f:
        content = f.read()
    match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    return {}

tokens = load_design_tokens()
colors = tokens.get("colors", {})

# CSS
st.markdown("""
<style>
:root {
    --brand-primary: #3B2F9E;
    --brand-primary-hover: #4A3FC0;
    --accent-growth: #0FA958;
    --accent-wealth: #D4A80D;
    --accent-clarity: #0A72EF;
    --accent-signal: #7A4DFF;
    --neutral-975: #061B31;
    --neutral-700: #273951;
    --neutral-500: #64748D;
    --neutral-300: #B8BDC6;
    --neutral-200: #E5EDF5;
    --neutral-100: #F0F4F8;
    --neutral-50: #F7F9FC;
    --neutral-0: #FFFFFF;
    --border-shadow: rgba(0,0,0,0.08) 0px 0px 0px 1px;
    --radius-sm: 4px;
    --radius-md: 6px;
    --radius-lg: 8px;
    --space-md: 16px;
}
.stApp { background-color: #F7F9FC; font-family: 'Source Sans 3', system-ui, sans-serif; }
h1, h2, h3, h4 { font-family: 'Source Sans 3', system-ui, sans-serif; color: #061B31; font-weight: 300; line-height: 1.1; }
h1 { font-size: 2.5rem; letter-spacing: -0.02em; }
h2 { font-size: 1.625rem; letter-spacing: -0.01em; }
h3 { font-size: 1.375rem; letter-spacing: -0.01em; }
.stButton > button { background-color: #3B2F9E !important; color: white !important; border: none !important; border-radius: 4px !important; padding: 12px 20px !important; font-family: 'Source Sans 3' !important; font-weight: 400 !important; font-size: 1rem !important; transition: background-color 120ms ease !important; }
.stButton > button:hover { background-color: #4A3FC0 !important; }
.stButton > button[kind="secondary"] { background-color: transparent !important; color: #3B2F9E !important; border: 1px solid #3B2F9E !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #E5EDF5; }
.stTabs [data-baseweb="tab"] { padding: 12px 16px !important; font-weight: 500 !important; font-family: 'Source Sans 3' !important; color: #64748D !important; border-bottom: 2px solid transparent !important; margin-bottom: -1px !important; }
.stTabs [aria-selected="true"] { color: #3B2F9E !important; border-bottom-color: #3B2F9E !important; }
.tab-growth [aria-selected="true"] { color: #0FA958 !important; border-bottom-color: #0FA958 !important; }
.tab-wealth [aria-selected="true"] { color: #D4A80D !important; border-bottom-color: #D4A80D !important; }
.tab-clarity [aria-selected="true"] { color: #0A72EF !important; border-bottom-color: #0A72EF !important; }
.tab-signal [aria-selected="true"] { color: #7A4DFF !important; border-bottom-color: #7A4DFF !important; }
.metric-card { background: #FFFFFF; border-radius: 6px; padding: 16px; box-shadow: rgba(0,0,0,0.08) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 4px -2px; border: 1px solid #E5EDF5; border-top: 3px solid #0FA958; }
.metric-card-wealth { border-top-color: #D4A80D; }
.metric-card-clarity { border-top-color: #0A72EF; }
.metric-card-signal { border-top-color: #7A4DFF; }
.data-meta { display: flex; gap: 16px; font-size: 0.75rem; color: #64748D; font-family: 'Source Sans 3', system-ui, sans-serif; }
.confidence-badge { display: inline-flex; padding: 2px 8px; border-radius: 9999px; font-size: 0.625rem; font-weight: 500; font-family: 'Geist Mono', monospace; text-transform: uppercase; }
.confidence-high { background: rgba(21,190,83,0.15); color: #108C3D; border: 1px solid rgba(21,190,83,0.3); }
.confidence-medium { background: rgba(212,168,13,0.15); color: #9B6829; border: 1px solid #D4A80D; }
.confidence-low { background: rgba(234,34,97,0.15); color: #C41A4D; border: 1px solid #EA2261; }
.methodology-expander { background: #F0F4F8; border: 1px solid #E5EDF5; border-radius: 6px; padding: 16px; margin-top: 16px; }
#MainMenu { visibility: hidden; } footer { visibility: hidden; } header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("<div style='text-align: center; padding: 1rem 0;'><h1 style='font-size: 1.5rem; margin-bottom: 0;'>Career Intelligence</h1><p style='color: #64748D; font-size: 0.875rem;'>Toronto job market, decoded.</p></div>", unsafe_allow_html=True)
    page = st.radio("Insights", ["📈 Skill Demand", "💰 Salary Ranges", "🎯 Role Fit", "📊 Market Context"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Filters**")
    date_range = st.selectbox("Time Period", ["Last 12 months", "Last 6 months", "Last 3 months", "Year to Date"], index=0)
    st.divider()
    st.markdown("**Data Freshness**")
    for source, date in {"Job Bank Postings": "Jun 3, 2026", "Job Bank Wages": "2025", "StatsCan JVWS": "Q1 2026", "Indeed Trends": "Jun 2026"}.items():
        st.caption(f"{source}: {date}")
    st.divider()
    st.markdown("**Confidence Levels**")
    st.markdown('<div style="display: flex; flex-direction: column; gap: 4px; font-size: 0.75rem;"><span><span class="confidence-badge confidence-high">High</span> Direct from official sources</span><span><span class="confidence-badge confidence-medium">Medium</span> Derived with assumptions</span><span><span class="confidence-badge confidence-low">Low</span> Estimated / user-dependent</span></div>', unsafe_allow_html=True)

st.title("Career Intelligence Dashboard")
st.caption("Transforming 50,000+ monthly Toronto job postings into actionable career intelligence")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "pipeline"))

try:
    from insights import (get_skill_demand_trends, get_emerging_skills, get_salary_by_role, compute_role_fit, get_market_context, get_data_freshness, get_confidence_summary)
    INSIGHTS_AVAILABLE = True
except ImportError as e:
    INSIGHTS_AVAILABLE = False
    st.warning(f"Insights module not fully available: {e}")

# ===== SKILL DEMAND =====
if page == "📈 Skill Demand":
    st.header("Skill Demand Trends")
    st.caption("Top skills mentioned in Toronto job postings, monthly trends, and emerging skills")
    st.markdown('<div class="data-meta"><span class="confidence-badge confidence-high">High Confidence</span><span>Source: Job Bank Open Data (50K+ postings) | NLP extraction 73% confidence</span></div>', unsafe_allow_html=True)
    with st.expander("📋 Methodology", expanded=False):
        st.markdown("""
**Data Source:** Job Bank Open Data monthly CSVs (Jan 2023 – present), filtered for Toronto CMA municipalities.

**Skill Extraction:** NLP pipeline using spaCy + rapidfuzz against Lightcast Open Skills taxonomy (34K+ skills).
Confidence threshold: 80% fuzzy match. Estimated precision: 73%.

**Processing:** Monthly aggregation of unique skill mentions per posting. Deduplicated by (title, NOC, location, date).

**Limitations:** Unstructured job requirement text varies in quality. Some skills implied but not explicitly stated.
Monthly lag: 2-4 weeks after posting date.
""")
    if INSIGHTS_AVAILABLE:
        with st.spinner("Loading skill demand data..."):
            trends_df = get_skill_demand_trends()
            emerging_df = get_emerging_skills()
        if not trends_df.empty:
            latest_month = trends_df["month"].max()
            current = trends_df[trends_df["month"] == latest_month].head(20)
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader(f"Top Skills — {latest_month.strftime('%B %Y')}")
                st.dataframe(current[["rank", "skill_name", "category", "postings_count"]].rename(columns={"rank": "Rank", "skill_name": "Skill", "category": "Category", "postings_count": "Postings"}), hide_index=True, use_container_width=True)
            with col2:
                st.subheader("🚀 Emerging Skills")
                if not emerging_df.empty:
                    for _, row in emerging_df.head(10).iterrows():
                        st.markdown(f"<div style='padding: 8px; background: #E6F7EB; border-radius: 4px; margin: 4px 0;'><strong>{row['skill_name']}</strong><br><small>+{row['qoq_growth']*100:.0f}% QoQ | {int(row['current_cnt'])} postings</small></div>", unsafe_allow_html=True)
                else:
                    st.info("No emerging skills detected this period")
            st.subheader("Monthly Trend (Top 10 Skills)")
            top10_skills = current.head(10)["skill_name"].tolist()
            trend_subset = trends_df[trends_df["skill_name"].isin(top10_skills)]
            import plotly.express as px
            fig = px.line(trend_subset, x="month", y="postings_count", color="skill_name", title="Monthly Posting Count for Top 10 Skills")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Source Sans 3", font_color="#273951", xaxis_title="Month", yaxis_title="Postings")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No skill demand data loaded yet. Run the data pipeline first.")
    else:
        st.info("Run  to load data and enable this view.")
