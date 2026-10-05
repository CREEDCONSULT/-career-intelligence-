import duckdb
import pytest

from llm.sql_guard import GuardError, run_guarded, validate_select


def test_accepts_select():
    validate_select("SELECT skill_name, count(*) FROM job_skills GROUP BY 1")


def test_accepts_cte_and_window():
    validate_select(
        "WITH t AS (SELECT noc_code, count(*) c FROM job_postings GROUP BY 1) "
        "SELECT noc_code, c, row_number() OVER (ORDER BY c DESC) rn FROM t"
    )


@pytest.mark.parametrize("bad", [
    "DELETE FROM job_postings",
    "DROP TABLE job_skills",
    "UPDATE job_postings SET title='x'",
    "INSERT INTO job_skills VALUES (1)",
    "TRUNCATE job_postings",
])
def test_rejects_non_select(bad):
    with pytest.raises(GuardError):
        validate_select(bad)


def test_rejects_multiple_statements():
    with pytest.raises(GuardError):
        validate_select("SELECT 1; DROP TABLE job_postings")


def test_rejects_cte_with_hidden_write():
    # a SELECT that smuggles a DML node should be caught by the node scan
    with pytest.raises(GuardError):
        validate_select("SELECT * FROM (DELETE FROM job_postings RETURNING *)")


def test_run_guarded_returns_df():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER); INSERT INTO t VALUES (1),(2),(3)")
    df = run_guarded(con, "SELECT sum(a) AS s FROM t", row_cap=10)
    assert int(df.iloc[0]["s"]) == 6


def test_run_guarded_blocks_writes():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    with pytest.raises(GuardError):
        run_guarded(con, "INSERT INTO t VALUES (1)", row_cap=10)


def test_run_guarded_caps_rows():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    con.execute("INSERT INTO t SELECT * FROM range(100)")
    df = run_guarded(con, "SELECT a FROM t", row_cap=5)
    assert len(df) == 5
