"""Page: Career Advisor (grounded chat)."""
import os
from pathlib import Path

import duckdb
import streamlit as st

from ._shared import data_meta, methodology

METHODOLOGY = """
**How it works:** Your question is turned into specific data questions, each answered by executed SQL
(the same grounded Ask engine), and the advice is composed strictly from those results — then
fact-checked before you see it. Questions the data can't answer are declined, not guessed. Every
answer shows its data sources.
"""

_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _ROOT / "data" / "processed" / "career_intel.duckdb"
SESSION_LIMIT = int(os.getenv("ADVISOR_SESSION_LIMIT", "12"))
DAILY_TOKEN_CAP = int(os.getenv("ASK_DAILY_TOKEN_CAP", "200000"))


@st.cache_resource
def _gateway():
    from llm.cache import ResponseCache
    from llm.config import LLMConfig
    from llm.gateway import Gateway
    return Gateway(LLMConfig.from_env(), cache=ResponseCache(_ROOT / "data" / "processed" / "llm_cache.duckdb"))


@st.cache_resource
def _usage():
    from llm.usage import DailyUsage
    return DailyUsage(_ROOT / "data" / "processed" / "llm_usage.json")


def render(date_range: str = "Last 12 months") -> None:
    st.header("Career Advisor")
    st.caption("Ask for guidance — grounded in Toronto job-market data, or it declines")
    data_meta("Medium", "Plan → grounded SQL → fact-checked advice · declines out-of-scope")
    methodology(METHODOLOGY)

    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")):
        st.info("Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) to enable the advisor.")
        return

    history = st.session_state.setdefault("advisor_history", [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for src in msg.get("sources", []):
                with st.expander(f"🔎 Source: {src['q'][:60]}"):
                    st.code(src["sql"] or "", language="sql")

    prompt = st.chat_input("e.g. I'm a marketing coordinator — what should I learn to earn more?")
    if not prompt:
        return

    if len([m for m in history if m["role"] == "user"]) >= SESSION_LIMIT:
        st.warning(f"Session limit reached ({SESSION_LIMIT} messages). Refresh to continue.")
        return
    usage = _usage()
    if usage.today() >= DAILY_TOKEN_CAP:
        st.warning("The daily usage cap for this demo has been reached — please come back tomorrow.")
        return

    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    from llm.features.advisor import advise

    gw = _gateway()
    before = gw.tokens_used
    with st.chat_message("assistant"):
        with st.spinner("Consulting the data…"):
            con = duckdb.connect(str(DB_PATH), read_only=True)
            try:
                adv = advise(prompt, con, gw)
            finally:
                con.close()
        st.markdown(adv.answer)
        sources = [{"q": s.question, "sql": s.sql} for s in adv.sources]
        for src in sources:
            with st.expander(f"🔎 Source: {src['q'][:60]}"):
                st.code(src["sql"] or "", language="sql")
    usage.add(gw.tokens_used - before)
    history.append({"role": "assistant", "content": adv.answer, "sources": sources})
