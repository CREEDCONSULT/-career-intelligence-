"""Page: Ask (grounded text-to-SQL Q&A)."""
import os

import duckdb
import streamlit as st

from ._shared import data_meta, methodology, money_safe

METHODOLOGY = """
**How it works:** Your question is sent to an LLM with the database schema (never the data). The
model writes a **DuckDB SELECT query**, which is validated (SELECT-only) and executed here — so every
number comes from the database, not the model. The answer is then checked: any number in the prose
must appear in the query result, or it falls back to showing the table only.

**Provider-agnostic** (LiteLLM): Claude by default, swappable to OpenAI/local via env.
**Measured:** 80% execution accuracy + 0 wrong numbers shown on a 20-question gold set.
"""

_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
DB_PATH = _ROOT / "data" / "processed" / "career_intel.duckdb"

# Abuse/cost guards for public deployments
SESSION_LIMIT = int(os.getenv("ASK_SESSION_LIMIT", "10"))
DAILY_TOKEN_CAP = int(os.getenv("ASK_DAILY_TOKEN_CAP", "200000"))


@st.cache_resource
def _gateway():
    from llm.cache import ResponseCache
    from llm.config import LLMConfig
    from llm.gateway import Gateway
    cache = ResponseCache(_ROOT / "data" / "processed" / "llm_cache.duckdb")
    return Gateway(LLMConfig.from_env(), cache=cache)


@st.cache_resource
def _usage():
    from llm.usage import DailyUsage
    return DailyUsage(_ROOT / "data" / "processed" / "llm_usage.json")


EXAMPLES = [
    "What are the top 10 skills by number of postings?",
    "Which occupations have the highest median wage?",
    "Which skills are growing fastest month over month?",
    "How many job vacancies are there in Toronto?",
    "What is the AI share of postings, and is it rising?",
    "Which roles have the most openings right now?",
]


@st.cache_data(ttl=3600)
def _overview():
    from pipeline.insights import get_dataset_overview
    return get_dataset_overview()


def _overview_panel() -> None:
    try:
        ov = _overview()
    except Exception:
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Job postings", f"{ov['postings']:,}" if ov.get("postings") else "—")
    c2.metric("Occupations", f"{ov['occupations']:,}" if ov.get("occupations") else "—")
    c3.metric("Distinct skills", f"{ov['skills']:,}" if ov.get("skills") else "—")
    span = f"{str(ov.get('date_min'))[:7]} → {str(ov.get('date_max'))[:7]}" if ov.get("date_min") else "—"
    c4.metric("Coverage", span)
    st.markdown(
        "<div style='background:#F0F4F8;border:1px solid #E5EDF5;border-radius:6px;padding:10px 14px;"
        "font-size:0.85rem;color:#273951;margin:4px 0 8px;'>"
        "<strong>What you can ask about:</strong> in-demand <em>skills</em>, <em>salaries</em> by "
        "occupation, job <em>vacancies</em>, hiring <em>momentum</em>, and the <em>AI share</em> of "
        "postings — all for the Toronto / GTA market.</div>",
        unsafe_allow_html=True,
    )


def render(date_range: str = "Last 12 months") -> None:
    st.header("Ask the Data")
    st.caption("Ask a question about the Toronto job market in plain English")
    data_meta("High", "Grounded text-to-SQL · numbers come from the database, never the model")
    methodology(METHODOLOGY)

    _overview_panel()

    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")):
        st.info("Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) in your environment to enable Ask.")
        return

    st.markdown("**Try one of these — or type your own:**")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, key=f"ask_ex_{i}", use_container_width=True):
            st.session_state["ask_q"] = ex
    question = st.text_input(
        "Your question", key="ask_q",
        placeholder="e.g. Which skills are growing fastest in Toronto?",
    )

    if not question:
        return

    # --- guards: per-session question cap + shared daily token cap ---
    asked = st.session_state.get("ask_count", 0)
    if asked >= SESSION_LIMIT:
        st.warning(f"Session limit reached ({SESSION_LIMIT} questions). Refresh to start a new session.")
        return
    usage = _usage()
    if usage.today() >= DAILY_TOKEN_CAP:
        st.warning("The daily usage cap for this demo has been reached — please come back tomorrow.")
        return

    from llm.features.ask import ask

    gw = _gateway()
    tokens_before = gw.tokens_used
    with st.spinner("Writing SQL, running it, and checking the answer…"):
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            ans = ask(question, con, gw)
        finally:
            con.close()
    st.session_state["ask_count"] = asked + 1
    usage.add(gw.tokens_used - tokens_before)

    if ans.error and ans.table is None:
        st.error(f"Couldn't answer that one (SQL failed after retries): {ans.error}")
        if ans.sql:
            st.code(ans.sql, language="sql")
        return

    if ans.grounded and ans.prose:
        st.success(money_safe(ans.prose))
    elif ans.prose:
        st.warning("Answer shown as data only (the drafted summary couldn't be verified against the result).")

    if ans.table is not None:
        st.dataframe(ans.table, hide_index=True, use_container_width=True)

    with st.expander("🔎 Generated SQL (auditable)"):
        st.code(ans.sql or "", language="sql")
