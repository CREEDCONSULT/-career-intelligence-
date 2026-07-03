"""Page: Monthly Market Brief (renders the latest generated brief)."""
from pathlib import Path

import streamlit as st

from ._shared import data_meta, methodology, money_safe

METHODOLOGY = """
**How it's made:** Once a month the pipeline computes the section figures (postings, skills,
salaries, macro signals) directly from the database, then an LLM writes a short narrative for each
section. Every paragraph is verified: any number in the text must match the computed figures exactly,
or the section is published as plain verified statistics instead. Generate with
`python scripts/make_brief.py`.
"""

BRIEFS_DIR = Path(__file__).resolve().parents[2] / "docs" / "briefs"


def render(date_range: str = "Last 12 months") -> None:
    st.header("Monthly Market Brief")
    data_meta("High", "Grounded narrative over pipeline-computed figures")
    methodology(METHODOLOGY)

    briefs = sorted(BRIEFS_DIR.glob("*.md"), reverse=True) if BRIEFS_DIR.exists() else []
    if not briefs:
        st.info("No briefs generated yet — run `python scripts/make_brief.py` (requires an LLM API key).")
        return

    labels = [p.stem for p in briefs]
    pick = st.selectbox("Edition", labels, index=0)
    md = (BRIEFS_DIR / f"{pick}.md").read_text(encoding="utf-8")
    st.markdown(money_safe(md))
    st.download_button("Download Markdown", md, file_name=f"market-brief-{pick}.md")
