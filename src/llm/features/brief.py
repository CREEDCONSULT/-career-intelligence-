"""Phase 2: auto-generated monthly market brief.

Every section's figures are computed deterministically from DuckDB; the LLM only
narrates them. Each paragraph is gated by ``grounding.grounded`` — if the model
invents a number twice, the section falls back to a deterministic bullet list of
the same stats. No invented number can ever ship.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

from llm.grounding import grounded
from pipeline.market import load_market


@dataclass
class Section:
    title: str
    stats_df: pd.DataFrame
    stats_text: str
    prose: str
    grounded: bool


def _section(gw, title: str, stats_df: pd.DataFrame, stats_text: str) -> Section:
    market = load_market().name
    prompt = (
        f"Write a 2-4 sentence paragraph for the '{title}' section of a monthly "
        f"{market} job-market brief. Professional, plain tone. Prose only — no heading, "
        f"no title line, no bullet points. Use ONLY the figures below, verbatim — do not "
        f"compute, round, or invent any number. You may compare the given figures to each "
        f"other (higher/lower/led/followed), but do NOT add causes, sector labels, trends, "
        f"or implications that are not stated in FIGURES.\n\nFIGURES:\n{stats_text}"
    )
    prose = ""
    for attempt in range(2):
        resp = gw.complete([{"role": "user", "content": prompt}], tier="interactive")
        prose = (resp.text or "").strip()
        # strip a redundant leading title line the model sometimes adds
        first, _, rest = prose.partition("\n")
        if title.lower() in first.lower().replace("*", "").replace("#", "").strip().lower() and rest.strip():
            prose = rest.strip()
        ok, _ = grounded(prose, stats_df, allow_sums=True)
        if ok:
            return Section(title, stats_df, stats_text, prose, True)
        prompt += "\n\nYour previous draft used numbers not in FIGURES. Use only those exact figures."
    # deterministic fallback: the stats themselves, as bullets
    bullets = "\n".join(f"- {line}" for line in stats_text.splitlines() if line.strip())
    return Section(title, stats_df, stats_text, bullets, False)


def _latest_month(con) -> str:
    row = con.execute(
        "SELECT strftime(max(posted_date), '%Y-%m') FROM job_postings WHERE posted_date IS NOT NULL"
    ).fetchone()
    return row[0]


def _overview_stats(con, month: str):
    cur, prev = con.execute(f"""
        WITH m AS (SELECT strftime(posted_date, '%Y-%m') AS mo, count(*) AS n
                   FROM job_postings WHERE posted_date IS NOT NULL GROUP BY 1)
        SELECT (SELECT n FROM m WHERE mo = '{month}'),
               (SELECT n FROM m WHERE mo = strftime((DATE '{month}-01' - INTERVAL '1 month'), '%Y-%m'))
    """).fetchone()
    cur = cur or 0
    prev = prev or 0
    mom = round((cur - prev) / prev * 100, 1) if prev else 0.0
    top = con.execute(f"""
        SELECT m.title, count(*) AS n FROM job_postings p
        JOIN noc_mapping m ON p.noc_code = m.noc_code
        WHERE strftime(p.posted_date, '%Y-%m') = '{month}'
        GROUP BY 1 ORDER BY n DESC LIMIT 1
    """).fetchone() or ("n/a", 0)
    df = pd.DataFrame({"v": [cur, prev, mom, top[1]]})
    text = (
        f"postings this month: {cur}\n"
        f"postings prior month: {prev}\n"
        f"month-over-month change: {mom}%\n"
        f"most-posted occupation: {top[0]} ({top[1]} postings)"
    )
    return df, text


def _skills_stats(con, month: str):
    rows = con.execute(f"""
        SELECT skill_name, count(DISTINCT job_id) AS n FROM job_skills
        WHERE strftime(posted_date, '%Y-%m') = '{month}'
        GROUP BY 1 ORDER BY n DESC LIMIT 5
    """).fetchall()
    df = pd.DataFrame({"v": [r[1] for r in rows]})
    text = "\n".join(f"top skill #{i+1}: {r[0]} ({r[1]} postings)" for i, r in enumerate(rows))
    return df, text or "no skill data"


def _salary_stats(con, month: str):
    region = load_market().economic_region_name
    med = con.execute(f"""
        SELECT round(median(median_wage), 2) FROM wages_job_bank
        WHERE region = '{region}' AND year = (SELECT max(year) FROM wages_job_bank)
    """).fetchone()[0]
    rows = con.execute(f"""
        SELECT m.title, round(w.median_wage, 2) FROM wages_job_bank w
        JOIN noc_mapping m ON w.noc_code = m.noc_code
        WHERE w.region = '{region}' AND w.year = (SELECT max(year) FROM wages_job_bank)
        ORDER BY w.median_wage DESC LIMIT 3
    """).fetchall()
    vals = [med] + [r[1] for r in rows]
    df = pd.DataFrame({"v": vals})
    text = f"median hourly wage across roles: ${med}\n" + "\n".join(
        f"highest-paid role #{i+1}: {r[0]} (${r[1]}/hr median)" for i, r in enumerate(rows)
    )
    return df, text


def _macro_stats(con, month: str):
    market = load_market().name

    def latest(metric, geo):
        row = con.execute(
            "SELECT round(value, 1) FROM indeed_trends WHERE metric = ? AND geography = ? "
            "AND date IS NOT NULL ORDER BY date DESC LIMIT 1", [metric, geo]
        ).fetchone()
        return row[0] if row else None

    idx = latest("postings_index", market)
    ai = latest("ai_share", "Canada")
    wage_row = con.execute(
        "SELECT round(value * 100, 1) FROM indeed_trends WHERE metric = 'wage_growth' "
        "AND date IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    wage = wage_row[0] if wage_row else None
    # 100 / 2020 are baseline constants from the index definition — allowable in prose
    vals = [v for v in (idx, ai, wage) if v is not None] + [100, 2020]
    df = pd.DataFrame({"v": vals})
    lines = []
    if idx is not None:
        lines.append(f"{market} Indeed postings index (Feb 2020 = 100): {idx}")
    if ai is not None:
        lines.append(f"AI share of Canadian postings: {ai}%")
    if wage is not None:
        lines.append(f"Canadian posted wage growth (YoY): {wage}%")
    return df, "\n".join(lines) or "no macro data"


def assemble_brief(month_label: str, sections: list[Section]) -> str:
    market = load_market().name
    parts = [
        f"# {market} Job Market Brief — {month_label}",
        "",
        "_Auto-generated from official open data (Job Bank, Statistics Canada, Indeed "
        "Hiring Lab). Every figure is computed by the data pipeline; narrative text is "
        "verified against those figures before publication._",
        "",
    ]
    for s in sections:
        parts += [f"## {s.title}", "", s.prose, ""]
    parts += [
        "---",
        f"*Generated {date.today().isoformat()} · Career Intelligence Dashboard · creedConsult. "
        "Contains information licensed under the Open Government Licence – Canada; "
        "Statistics Canada, Table 14-10-0444-01; Indeed Hiring Lab (CC-BY-4.0).*",
    ]
    return "\n".join(parts)


def make_brief(con: duckdb.DuckDBPyConnection, gw, month: str | None = None) -> str:
    month = month or _latest_month(con)
    month_label = pd.Timestamp(f"{month}-01").strftime("%B %Y")
    builders = [
        ("Market Overview", _overview_stats),
        ("Skill Demand", _skills_stats),
        ("Salaries", _salary_stats),
        ("Macro Signals", _macro_stats),
    ]
    sections = []
    for title, build in builders:
        stats_df, stats_text = build(con, month)
        sections.append(_section(gw, title, stats_df, stats_text))
    return assemble_brief(month_label, sections)
