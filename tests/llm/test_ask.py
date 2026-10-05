import duckdb

from llm.features.ask import Answer, ask
from llm.gateway import Response


class FakeGW:
    """Gateway stub returning queued responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages, tier="interactive", cache_prefix=None):
        self.calls.append(messages)
        return Response(text=self.responses.pop(0), tokens=1)


def _con():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER); INSERT INTO t VALUES (1),(2),(3)")
    return con


def test_ask_happy_path():
    gw = FakeGW(["SELECT sum(a) AS total FROM t", "The total is 6."])
    ans = ask("what is the sum of a?", _con(), gw)
    assert isinstance(ans, Answer)
    assert ans.sql.strip().upper().startswith("SELECT")
    assert int(ans.table.iloc[0]["total"]) == 6
    assert "6" in ans.prose
    assert ans.grounded is True


def test_ask_strips_markdown_fences():
    gw = FakeGW(["```sql\nSELECT sum(a) AS total FROM t\n```", "The total is 6."])
    ans = ask("sum?", _con(), gw)
    assert "```" not in ans.sql
    assert int(ans.table.iloc[0]["total"]) == 6


def test_ask_self_corrects_bad_sql():
    gw = FakeGW([
        "SELECT nonexistent_col FROM t",          # fails execution
        "SELECT count(*) AS c FROM t",            # corrected
        "There are 3 rows.",                       # narration
    ])
    ans = ask("how many rows?", _con(), gw)
    assert int(ans.table.iloc[0]["c"]) == 3
    assert ans.grounded is True


def test_ask_flags_ungrounded_narration():
    gw = FakeGW([
        "SELECT sum(a) AS total FROM t",  # -> 6
        "The total is 999.",              # invented number
        "The total is 999 again.",        # regeneration still wrong
    ])
    ans = ask("sum?", _con(), gw)
    assert ans.grounded is False


def test_ask_returns_error_when_sql_unfixable():
    gw = FakeGW([
        "SELECT bad FROM t",   # fails
        "SELECT worse FROM t", # still fails
        "SELECT nope FROM t",  # still fails (retries exhausted)
    ])
    ans = ask("broken", _con(), gw)
    assert ans.table is None
    assert ans.error is not None
