from pathlib import Path

import duckdb
import pytest

from llm.eval.runner import execution_accuracy, load_gold, validate_gold

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "processed" / "career_intel.duckdb"


def test_execution_accuracy_matches_equivalent_sql():
    con = duckdb.connect()
    con.execute("CREATE TABLE t(a INTEGER); INSERT INTO t VALUES (1),(2)")
    assert execution_accuracy(con, "SELECT sum(a) AS s FROM t", "SELECT (1+2) AS s")
    assert not execution_accuracy(con, "SELECT count(*) AS c FROM t", "SELECT sum(a) AS c FROM t")


def test_execution_accuracy_is_row_order_insensitive():
    con = duckdb.connect()
    con.execute("CREATE TABLE t(a INTEGER); INSERT INTO t VALUES (1),(2),(3)")
    assert execution_accuracy(con, "SELECT a FROM t ORDER BY a", "SELECT a FROM t ORDER BY a DESC")


def test_gold_set_loads_and_is_sized():
    gold = load_gold()
    assert len(gold) >= 20
    assert all("question" in g and "reference_sql" in g for g in gold)


@pytest.mark.skipif(not DB.exists(), reason="DB not built")
def test_all_gold_reference_sql_execute():
    con = duckdb.connect(str(DB), read_only=True)
    failures = validate_gold(con, load_gold())
    assert failures == [], f"invalid gold reference SQL:\n" + "\n".join(failures)
