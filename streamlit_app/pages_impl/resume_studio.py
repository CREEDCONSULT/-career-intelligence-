"""Page: Resume & Cover Letter Studio.

Upload a PDF/DOCX (parsed token-free via markitdown) or paste text, then:
market fit & gaps, market-aware review, tailoring to a target role, and a
grounded cover letter. Rewrites never fabricate experience; market facts come
from the real Toronto data.
"""
import os
from pathlib import Path

import duckdb
import streamlit as st

from ._shared import data_meta, methodology, money_safe

METHODOLOGY = """
**Parsing is token-free:** uploaded PDFs/DOCX are converted to text with the markitdown library —
no LLM call — so the model only ever sees the extracted text. **Fit & gaps** matches your resume to
real in-demand Toronto occupations (local embeddings, no API). **Review, Tailor, and Cover Letter**
use the LLM, grounded in real market facts, and are instructed never to invent experience you don't
have — they reorganize and emphasize what's already in your resume.
"""

_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _ROOT / "data" / "processed" / "career_intel.duckdb"
MAX_CHARS = 6000
SESSION_LIMIT = int(os.getenv("ASK_SESSION_LIMIT", "10"))
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


def _has_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def _budget_ok() -> bool:
    if _usage().today() >= DAILY_TOKEN_CAP:
        st.warning("The daily usage cap for this demo has been reached — please come back tomorrow.")
        return False
    return True


def _run_llm(fn, *args):
    """Call an LLM feature fn(*args, gw), tracking tokens against the daily cap."""
    gw = _gateway()
    before = gw.tokens_used
    out = fn(*args, gw)
    _usage().add(gw.tokens_used - before)
    return out


@st.cache_data(ttl=3600)
def _role_options():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        rows = con.execute("""
            SELECT m.title, count(*) AS n FROM job_postings p
            JOIN noc_mapping m ON p.noc_code = m.noc_code
            WHERE p.noc_code IS NOT NULL AND p.noc_code != ''
            GROUP BY 1 ORDER BY n DESC LIMIT 120
        """).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def _role_facts(title: str):
    """Grounded facts for a target occupation: demanded skills + median wage + postings."""
    from pipeline.insights import _skills_table
    from pipeline.market import load_market
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        st_tbl = _skills_table(con)
        region = load_market().economic_region_name
        skills = [r[0] for r in con.execute(f"""
            SELECT s.skill_name FROM {st_tbl} s JOIN job_postings p ON s.job_id = p.id
            JOIN noc_mapping m ON p.noc_code = m.noc_code
            WHERE m.title = ? GROUP BY 1 ORDER BY count(DISTINCT s.job_id) DESC LIMIT 12
        """, [title]).fetchall()]
        wage = con.execute(f"""
            SELECT round(median(w.median_wage), 2) FROM wages_job_bank w
            JOIN noc_mapping m ON w.noc_code = m.noc_code
            WHERE m.title = ? AND w.region = '{region}'
        """, [title]).fetchone()[0]
        postings = con.execute(
            "SELECT count(*) FROM job_postings p JOIN noc_mapping m ON p.noc_code = m.noc_code WHERE m.title = ?",
            [title]).fetchone()[0]
    finally:
        con.close()
    facts = f"Target role: {title}. In-demand skills: {', '.join(skills)}."
    if wage:
        facts += f" Median wage: ${wage}/hr."
    facts += f" Openings in the last 12 months: {postings}."
    return skills, facts


@st.cache_data(ttl=3600)
def _top_demanded_skills(n: int = 30):
    from pipeline.insights import _skills_table
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        st_tbl = _skills_table(con)
        rows = con.execute(f"""
            SELECT skill_name FROM {st_tbl}
            WHERE posted_date >= (SELECT max(posted_date) FROM {st_tbl}) - INTERVAL '3 months'
            GROUP BY 1 ORDER BY count(DISTINCT job_id) DESC LIMIT {n}
        """).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def _fit(resume_text: str) -> None:
    from llm.features.role_match import RoleIndex, build_role_docs, match_profile

    @st.cache_resource(show_spinner="Building the role index (one-time)...")
    def _index():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            docs = build_role_docs(con)
        finally:
            con.close()
        idx = RoleIndex()
        idx.build(docs)
        return idx

    st.caption("Your best-fit Toronto occupations (semantic match — no API key needed).")
    results = match_profile(resume_text, index=_index(), limit=5)
    for r in results:
        wage = f"${r['median_wage']:.2f}/hr median" if r["median_wage"] else "wage n/a"
        st.markdown(
            f"**{r['title']}** — score {r['score']:.2f} · {wage} · {r['demand']:,} postings",
        )

    st.divider()
    st.caption("Top in-demand skills you may be missing:")
    top = _top_demanded_skills(30)
    lc = resume_text.lower()
    gaps = [s for s in top if s.lower() not in lc][:10]
    if gaps:
        st.markdown(" ".join(f"`{g}`" for g in gaps))
    else:
        st.success("Your resume already reflects the most in-demand skills.")


def _needs_key_or_stop() -> bool:
    if not _has_key():
        st.info("This action needs an LLM API key (`ANTHROPIC_API_KEY`). Fit & gaps works without one.")
        return False
    return _budget_ok()


def _review(resume_text: str) -> None:
    if not st.button("Review my resume against the market", key="btn_review"):
        return
    if not _needs_key_or_stop():
        return
    from llm.features.resume import review
    facts = "Most in-demand Toronto skills right now: " + ", ".join(_top_demanded_skills(20))
    with st.spinner("Reviewing against current demand…"):
        out = _run_llm(review, resume_text, facts)
    st.markdown(money_safe(out))


def _tailor(resume_text: str) -> None:
    role = st.selectbox("Target role", _role_options(), key="tailor_role")
    if not st.button("Tailor my resume to this role", key="btn_tailor"):
        return
    if not _needs_key_or_stop():
        return
    from llm.features.resume import tailor
    skills, _ = _role_facts(role)
    with st.spinner(f"Tailoring for {role}…"):
        out = _run_llm(tailor, resume_text, role, skills)
    st.markdown(money_safe(out))
    st.download_button("Download tailored resume (Markdown)", out, file_name="tailored_resume.md")


def _cover(resume_text: str) -> None:
    role = st.selectbox("Target role", _role_options(), key="cover_role")
    if not st.button("Draft a cover letter for this role", key="btn_cover"):
        return
    if not _needs_key_or_stop():
        return
    from llm.features.resume import cover_letter
    _, facts = _role_facts(role)
    with st.spinner(f"Drafting a cover letter for {role}…"):
        out = _run_llm(cover_letter, resume_text, role, facts)
    st.markdown(money_safe(out))
    st.download_button("Download cover letter", out, file_name="cover_letter.md")


def render(date_range: str = "Last 12 months") -> None:
    st.header("Resume & Cover Letter Studio")
    st.caption("Upload your resume — see your market fit, get a review, tailor it, or draft a cover letter")
    data_meta("Medium", "Token-free parsing (markitdown) · grounded in Toronto data · never fabricates experience")
    methodology(METHODOLOGY)

    up = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
    pasted = st.text_area("…or paste it here", height=160, placeholder="Paste your resume text…")

    resume_text = ""
    if up is not None:
        from llm.features.resume import extract_text
        try:
            resume_text = extract_text(up.getvalue(), up.name)
        except Exception as e:  # noqa: BLE001
            st.error(f"Couldn't read that file: {e}")
    elif pasted.strip():
        resume_text = pasted.strip()

    if not resume_text:
        st.info("Upload a PDF/DOCX or paste your resume to begin.")
        return

    resume_text = resume_text[:MAX_CHARS]
    with st.expander("Parsed resume text"):
        st.text(resume_text[:2000] + ("…" if len(resume_text) >= 2000 else ""))

    t1, t2, t3, t4 = st.tabs(["🧭 Market fit & gaps", "📝 Review", "✏️ Tailor to a role", "✉️ Cover letter"])
    with t1:
        _fit(resume_text)
    with t2:
        _review(resume_text)
    with t3:
        _tailor(resume_text)
    with t4:
        _cover(resume_text)
