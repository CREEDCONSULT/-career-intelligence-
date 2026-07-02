import duckdb

from llm.schema import build_schema_card


def test_schema_card_lists_tables_columns_and_caveat():
    con = duckdb.connect()
    con.execute("CREATE TABLE job_skills (job_id INTEGER, skill_name TEXT, posted_date DATE)")
    con.execute("CREATE TABLE noc_mapping (noc_code TEXT, title TEXT)")
    card = build_schema_card(con)
    assert "job_skills" in card
    assert "skill_name" in card
    assert "noc_mapping" in card
    # the title-based-skills limitation note must be present
    assert "title" in card.lower()
    # join key documented
    assert "noc_code" in card


def test_schema_card_is_reasonably_sized():
    con = duckdb.connect()
    con.execute("CREATE TABLE job_skills (job_id INTEGER, skill_name TEXT)")
    card = build_schema_card(con)
    assert len(card) < 8000  # stays cache-friendly
