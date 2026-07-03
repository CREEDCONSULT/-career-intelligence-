from pathlib import Path

import duckdb
import pytest

from llm.features.role_match import RoleDoc, RoleIndex, build_role_docs, match_profile

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "processed" / "career_intel.duckdb"


@pytest.mark.skipif(not DB.exists(), reason="DB not built")
def test_build_role_docs_from_real_db():
    con = duckdb.connect(str(DB), read_only=True)
    docs = build_role_docs(con, min_postings=20)
    con.close()
    assert len(docs) > 100
    d = docs[0]
    assert d.noc_code and d.title and d.text
    assert d.demand > 0
    assert "Skills:" in d.text


def _synthetic_docs():
    return [
        RoleDoc("21231", "Software engineers and designers",
                "Software engineers and designers. Skills: Python, SQL, Cloud Computing, Code Review. Example titles: software engineer",
                demand=500, median_wage=55.0, top_skills=["Python", "SQL", "Cloud Computing"]),
        RoleDoc("63200", "Cooks",
                "Cooks. Skills: Food Preparation, Food Safety, Kitchen Operations. Example titles: cook, line cook",
                demand=3000, median_wage=18.0, top_skills=["Food Preparation", "Food Safety"]),
        RoleDoc("31301", "Registered nurses",
                "Registered nurses. Skills: Patient Care, Medication Administration, Clinical Assessment. Example titles: registered nurse",
                demand=800, median_wage=40.0, top_skills=["Patient Care", "Clinical Assessment"]),
    ]


def test_index_ranks_semantically_relevant_role_first():
    idx = RoleIndex()
    idx.build(_synthetic_docs())
    hits = idx.query("python developer with sql and cloud experience", limit=3)
    assert hits[0][0].title == "Software engineers and designers"


def test_match_profile_fuses_demand_and_reports_matched_skills():
    idx = RoleIndex()
    idx.build(_synthetic_docs())
    results = match_profile("experienced line cook, food prep and kitchen safety", index=idx, limit=3)
    top = results[0]
    assert top["title"] == "Cooks"
    assert 0 <= top["score"] <= 1
    assert top["median_wage"] == 18.0
    assert any("Food" in s for s in top["matched_skills"])
