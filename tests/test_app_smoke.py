"""Headless smoke test: every page renders against the real DuckDB without exceptions.

Skips automatically if the processed DB hasn't been built yet.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app" / "app.py"
DB = ROOT / "data" / "processed" / "career_intel.duckdb"

# Streamlit's AppTest does not add the script's dir to sys.path; do it here.
sys.path.insert(0, str(ROOT / "streamlit_app"))

pytestmark = pytest.mark.skipif(not DB.exists(), reason="DB not built; run downloaders + transform")

PAGES = ["📈 Skill Demand", "💰 Salary Ranges", "🎯 Role Fit", "📊 Market Context"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, f"exception on default load: {at.exception}"
    at.radio[0].set_value(page).run()
    assert not at.exception, f"exception rendering {page}: {at.exception}"
