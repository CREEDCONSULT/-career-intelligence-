#!/usr/bin/env python3
"""
Transform raw downloaded data -> processed DuckDB (career_intel.duckdb).

Run AFTER the downloaders. Idempotent: drops & recreates all tables each run.

Real-data specifics (see docs/superpowers/specs/2026-06-29-data-source-findings.md):
- Job Bank postings have NO requirements free-text; skills are extracted from
  Original Job Title + Job Title + NOC21 Code Name.
- Salaries are normalized to hourly equivalents.
- StatsCan JVWS rows are pivoted (Job vacancies / Average offered hourly wage).
- Indeed is stored long-format: (date, geography, metric, value, sector).
"""
import glob
import re
from pathlib import Path

import duckdb
import pandas as pd
from tqdm import tqdm

from pipeline.noc_mapper import NOCMapper, normalize_noc
from pipeline.salary import parse_salary_row
from pipeline.skill_matcher import SkillMatcher, build_skill_index

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "career_intel.duckdb"


def _col(df, *needles):
    for c in df.columns:
        norm = " ".join(str(c).lower().split())
        if any(n in norm for n in needles):
            return c
    return None


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    for t in ["job_postings", "job_skills", "wages_job_bank", "vacancies_statscan",
              "indeed_trends", "noc_mapping"]:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.execute("""
        CREATE TABLE job_postings (
            id INTEGER, source VARCHAR, source_id VARCHAR, title VARCHAR,
            noc_code VARCHAR, naics_code VARCHAR, location VARCHAR, location_normalized VARCHAR,
            vacancies INTEGER, salary_min DOUBLE, salary_max DOUBLE, salary_median DOUBLE,
            hours VARCHAR, employment_terms VARCHAR, requirements_text VARCHAR,
            posted_date DATE, scraped_date DATE)
    """)
    conn.execute("""
        CREATE TABLE job_skills (
            job_id INTEGER, skill_id VARCHAR, skill_name VARCHAR, category VARCHAR,
            posted_date DATE, noc_code VARCHAR)
    """)
    conn.execute("""
        CREATE TABLE wages_job_bank (
            noc_code VARCHAR, year INTEGER, region VARCHAR,
            min_wage DOUBLE, median_wage DOUBLE, max_wage DOUBLE)
    """)
    conn.execute("""
        CREATE TABLE vacancies_statscan (
            noc_code VARCHAR, year INTEGER, quarter INTEGER, region VARCHAR,
            vacancy_count INTEGER, avg_offered_wage DOUBLE)
    """)
    conn.execute("""
        CREATE TABLE indeed_trends (
            date DATE, geography VARCHAR, metric VARCHAR, value DOUBLE, sector VARCHAR)
    """)
    conn.execute("CREATE TABLE noc_mapping (noc_code VARCHAR, title VARCHAR, category VARCHAR)")
    return conn


def load_noc_mapping(conn):
    mapper = NOCMapper()
    rows = [{"noc_code": normalize_noc(c) or c, "title": t,
             "category": mapper.noc_to_category.get(c, "Unknown")}
            for c, t in mapper.noc_to_title.items()]
    df = pd.DataFrame(rows).drop_duplicates("noc_code")
    conn.register("noc_df", df)
    conn.execute("INSERT INTO noc_mapping SELECT noc_code, title, category FROM noc_df")
    print(f"  noc_mapping: {len(df):,}")
    return mapper


def load_job_bank_postings(conn):
    files = sorted(glob.glob(str(RAW_DIR / "job_bank_postings" / "toronto_*.csv")))
    if not files:
        print("  no Toronto postings files"); return 0
    next_id = 1
    total = 0
    for f in tqdm(files, desc="postings"):
        df = pd.read_csv(f, low_memory=False)
        title_c = _col(df, "job title") or "Job Title"
        orig_c = _col(df, "original job title")
        noc_c = _col(df, "noc21 code") and next((c for c in df.columns if "noc21 code" in c.lower() and "name" not in c.lower()), None)
        nocname_c = _col(df, "noc21 code name")
        city_c = _col(df, "city")
        naics_c = _col(df, "naics")
        vac_c = _col(df, "vacancy count")
        date_c = _col(df, "first posting date")
        emp_c = _col(df, "employment type")
        hours_c = _col(df, "hours per")

        out = pd.DataFrame()
        n = len(df)
        out["id"] = range(next_id, next_id + n)
        out["source"] = "job_bank"
        out["source_id"] = df[_col(df, "snapshot id")].astype(str) if _col(df, "snapshot id") else out["id"].astype(str)
        out["title"] = df[title_c].astype(str) if title_c in df else ""
        out["noc_code"] = df[noc_c].apply(normalize_noc) if noc_c else ""
        out["naics_code"] = df[naics_c].astype(str) if naics_c else ""
        out["location"] = df[city_c].astype(str) if city_c else ""
        out["location_normalized"] = out["location"].str.lower().str.strip()
        out["vacancies"] = pd.to_numeric(df[vac_c], errors="coerce").fillna(0).astype(int) if vac_c else 0
        sal = df.apply(lambda r: parse_salary_row({
            "Salary Minimum": r.get(_col(df, "salary minimum")),
            "Salary Maximum": r.get(_col(df, "salary maximum")),
            "Salary Per": r.get(_col(df, "salary per")),
        }), axis=1, result_type="expand")
        out["salary_min"] = sal["salary_min"]
        out["salary_max"] = sal["salary_max"]
        out["salary_median"] = sal["salary_median"]
        out["hours"] = df[hours_c].astype(str) if hours_c else ""
        out["employment_terms"] = df[emp_c].astype(str) if emp_c else ""
        orig = df[orig_c].fillna("").astype(str) if orig_c else ""
        nocname = df[nocname_c].fillna("").astype(str) if nocname_c else ""
        out["requirements_text"] = (out["title"].fillna("") + " " + orig + " " + nocname).str.strip()
        out["posted_date"] = pd.to_datetime(df[date_c], errors="coerce").dt.date if date_c else pd.NaT
        out["scraped_date"] = pd.Timestamp.now().date()

        conn.register("p_df", out)
        conn.execute("INSERT INTO job_postings SELECT * FROM p_df")
        next_id += n
        total += n
    print(f"  job_postings: {total:,}")
    return total


def extract_skills(conn, mapper):
    name_to_id, cat_by_id, name_by_id = build_skill_index()
    matcher = SkillMatcher(name_to_id)

    df = conn.execute(
        "SELECT id, requirements_text, posted_date, noc_code FROM job_postings "
        "WHERE requirements_text IS NOT NULL AND requirements_text != ''"
    ).df()
    records = []
    for row in tqdm(df.itertuples(index=False), total=len(df), desc="skills"):
        for s in matcher.extract(row.requirements_text):
            sid = s["skill_id"]
            records.append({
                "job_id": row.id, "skill_id": sid,
                "skill_name": name_by_id.get(sid, s["skill_name"]),
                "category": cat_by_id.get(sid, "Specialized Skill"),
                "posted_date": row.posted_date, "noc_code": row.noc_code,
            })
    if records:
        sk = pd.DataFrame(records)
        conn.register("sk_df", sk)
        conn.execute("INSERT INTO job_skills SELECT job_id, skill_id, skill_name, category, posted_date, noc_code FROM sk_df")
    print(f"  job_skills: {len(records):,}")


def load_wages(conn):
    files = sorted(glob.glob(str(RAW_DIR / "job_bank_wages" / "toronto_*.csv")))
    total = 0
    for f in files:
        year_m = re.search(r"wage(\d{4})", f)
        year = int(year_m.group(1)) if year_m else 0
        df = pd.read_csv(f, low_memory=False)
        noc_c = _col(df, "noc_cnp", "noc cnp")
        flag_c = _col(df, "annual_wage_flag", "salaire_annuel")
        low_c = _col(df, "low_wage", "salaire_minium")
        med_c = _col(df, "median_wage", "salaire_median")
        high_c = _col(df, "high_wage", "salaire_maximal")
        out = pd.DataFrame()
        out["noc_code"] = df[noc_c].apply(normalize_noc)
        out["year"] = year
        out["region"] = "Toronto"
        annual = pd.to_numeric(df[flag_c], errors="coerce").fillna(0).astype(int) if flag_c else 0
        div = annual.replace({1: 2080, 0: 1}) if hasattr(annual, "replace") else 1
        out["min_wage"] = pd.to_numeric(df[low_c], errors="coerce") / div
        out["median_wage"] = pd.to_numeric(df[med_c], errors="coerce") / div
        out["max_wage"] = pd.to_numeric(df[high_c], errors="coerce") / div
        out = out.dropna(subset=["median_wage"]).drop_duplicates(["noc_code", "year", "region"])
        conn.register("w_df", out)
        conn.execute("INSERT INTO wages_job_bank SELECT noc_code, year, region, min_wage, median_wage, max_wage FROM w_df")
        total += len(out)
    print(f"  wages_job_bank: {total:,}")


def load_statscan(conn):
    f = RAW_DIR / "statscan" / "jvws_toronto.csv"
    if not f.exists():
        print("  vacancies_statscan: 0 (StatsCan skipped)"); return
    df = pd.read_csv(f, low_memory=False)
    noc_c = _col(df, "national occupational classification")
    stat_c = _col(df, "statistics")
    ref_c = _col(df, "ref_date")
    val_c = _col(df, "value")
    df = df[df[noc_c].astype(str).str.contains(r"\[\d", regex=True, na=False)].copy()
    df["noc_code"] = df[noc_c].astype(str).str.extract(r"\[(\d+)\]")[0].apply(normalize_noc)
    df["year"] = df[ref_c].astype(str).str[:4].astype(int)
    df["month"] = pd.to_numeric(df[ref_c].astype(str).str[5:7], errors="coerce").fillna(1).astype(int)
    df["quarter"] = ((df["month"] - 1) // 3 + 1)
    df["value"] = pd.to_numeric(df[val_c], errors="coerce")
    vac = df[df[stat_c].str.contains("vacanc", case=False, na=False)].groupby(["noc_code", "year", "quarter"])["value"].sum().rename("vacancy_count")
    wage = df[df[stat_c].str.contains("wage", case=False, na=False)].groupby(["noc_code", "year", "quarter"])["value"].mean().rename("avg_offered_wage")
    out = pd.concat([vac, wage], axis=1).reset_index()
    out["region"] = "Toronto"
    out["vacancy_count"] = out["vacancy_count"].fillna(0).astype(int)
    conn.register("v_df", out)
    conn.execute("INSERT INTO vacancies_statscan SELECT noc_code, year, quarter, region, vacancy_count, avg_offered_wage FROM v_df")
    print(f"  vacancies_statscan: {len(out):,}")


def load_indeed(conn):
    base = RAW_DIR / "indeed"
    rows = []

    metro = base / "indeed_metro_postings.csv"
    if metro.exists():
        df = pd.read_csv(metro)
        df = df[df["Metro"].astype(str).str.contains("Toronto", case=False, na=False)]
        for _, r in df.iterrows():
            rows.append({"date": r["date"], "geography": "Toronto", "metric": "postings_index",
                         "value": r["indeed_job_postings_index"], "sector": None})

    ai = base / "indeed_ai_postings.csv"
    if ai.exists():
        df = pd.read_csv(ai)
        df = df[df["jobcountry"].astype(str).str.upper() == "CA"]
        for _, r in df.iterrows():
            rows.append({"date": r["date"], "geography": "Canada", "metric": "ai_share",
                         "value": r["AI_share_postings"], "sector": None})

    wage = base / "indeed_wage_by_country.csv"
    if wage.exists():
        df = pd.read_csv(wage)
        df = df[df["jobcountry"].astype(str).str.upper() == "CA"].copy()
        df["date"] = pd.to_datetime(df["month"], format="%b-%y", errors="coerce")
        for _, r in df.iterrows():
            rows.append({"date": r["date"].date() if pd.notna(r["date"]) else None,
                         "geography": "Canada", "metric": "wage_growth",
                         "value": r["posted_wage_growth_yoy"], "sector": None})

    if rows:
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        conn.register("i_df", df)
        conn.execute("INSERT INTO indeed_trends SELECT date, geography, metric, value, sector FROM i_df")
    print(f"  indeed_trends: {len(rows):,}")


def main():
    print("Initializing DuckDB...")
    conn = init_db()
    print("\n=== Loading Data ===")
    mapper = load_noc_mapping(conn)
    load_job_bank_postings(conn)
    load_wages(conn)
    load_statscan(conn)
    load_indeed(conn)
    print("\n=== Extracting Skills ===")
    extract_skills(conn, mapper)
    print("\n=== Verification ===")
    for t in ["job_postings", "job_skills", "wages_job_bank", "vacancies_statscan", "indeed_trends", "noc_mapping"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {count:,} rows")
    conn.close()
    print("\nTransform complete!")


if __name__ == "__main__":
    main()
