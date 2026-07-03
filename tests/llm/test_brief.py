from pathlib import Path

import duckdb
import pandas as pd
import pytest

from llm.features.brief import _section, assemble_brief, make_brief
from llm.gateway import Response

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "processed" / "career_intel.duckdb"


class FakeGW:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages, tier="interactive", cache_prefix=None):
        text = self.responses.pop(0) if self.responses else "no more"
        return Response(text=text, tokens=1)


def test_section_grounded_prose_is_used():
    df = pd.DataFrame({"metric": ["postings"], "value": [8000]})
    gw = FakeGW(["Postings reached 8000 this month."])
    s = _section(gw, "Market Overview", df, "postings: 8000")
    assert s.grounded is True
    assert "8000" in s.prose


def test_section_falls_back_to_stats_when_ungrounded():
    df = pd.DataFrame({"metric": ["postings"], "value": [8000]})
    gw = FakeGW(["Postings hit 9999.", "Still 9999, sorry."])  # both invented
    s = _section(gw, "Market Overview", df, "postings: 8000")
    assert s.grounded is False
    assert "8000" in s.prose  # deterministic fallback shows the real stats
    assert "9999" not in s.prose


def test_assemble_brief_contains_sections_and_attribution():
    df = pd.DataFrame({"v": [1]})
    from llm.features.brief import Section
    md = assemble_brief("May 2026", [Section("Overview", df, "v: 1", "text", True)])
    assert "May 2026" in md
    assert "## Overview" in md
    assert "Open Government Licence" in md


@pytest.mark.skipif(not DB.exists(), reason="DB not built")
def test_make_brief_end_to_end_with_fallbacks():
    # An LLM that always invents numbers -> every section must fall back, brief still assembles
    gw = FakeGW(["wrong 123456789"] * 20)
    con = duckdb.connect(str(DB), read_only=True)
    try:
        md = make_brief(con, gw)
    finally:
        con.close()
    assert md.startswith("#")
    assert "123456789" not in md  # no invented number survives
    for heading in ("Market Overview", "Skill Demand", "Salaries", "Macro Signals"):
        assert f"## {heading}" in md
