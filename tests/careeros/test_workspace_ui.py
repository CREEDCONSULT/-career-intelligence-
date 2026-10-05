"""UI-level workspace test: render + interact through Streamlit AppTest.

Goes beyond render-only smoke: seeds a temp database via the careeros stores,
then drives the Opportunities page through the AppTest runtime - the board,
the fit panel, the next-action banner, and a real state-machine button click.

The app's Career-Profile bootstrap still touches the default DB path, so the
base smoke (tests/test_app_smoke.py) covers render-only behavior there; this
test isolates the M1 workspace by pointing CAREEROS_DB at a temp DuckDB.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # tests/careeros/ -> repo root
APP = ROOT / "streamlit_app" / "app.py"

# Streamlit's AppTest does not add the script's dir to sys.path; do it here.
sys.path.insert(0, str(ROOT / "streamlit_app"))

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "ui.duckdb"
    monkeypatch.setenv("CAREEROS_DB", str(db))

    from careeros.application import ApplicationStore
    from careeros.evidence import Evidence, EvidenceStore
    from careeros.ingestion import ManualPasteAdapter, ingest
    from careeros.opportunity import OpportunityStore

    opps = OpportunityStore(db)
    evs = EvidenceStore(db)
    apps = ApplicationStore(db)

    opp = ingest(
        opps,
        ManualPasteAdapter(),
        (
            "Data Engineer at Demo Corp\n"
            "Remote, full-time. Python and SQL required. Apply by 2030-01-01."
        ),
    )
    evs.add(
        Evidence(
            evidence_id=0,
            type="employment",
            title="Data Engineer",
            description="Python and SQL pipelines at scale.",
            skills=["Python", "SQL"],
            provenance="test seed",
        )
    )
    app = apps.create_for_opportunity(opp.opportunity_id, provenance="test seed")
    return {"db": db, "opp": opp, "app": app, "apps": apps}


def _run_app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, f"exception on default load: {at.exception}"
    return at


def _open_opportunities(at):
    at.radio[0].set_value("Opportunities").run()
    assert not at.exception, f"exception on Opportunities: {at.exception}"
    return at


def test_workspace_renders_fit_and_next_action(temp_db):
    at = _open_opportunities(_run_app())
    # the seeded opportunity appears on the board / workspace header
    markdown = " ".join(m.value for m in at.markdown)
    assert "Data Engineer" in markdown
    assert "Demo Corp" in markdown
    # the NBA banner for a fresh DISCOVERED application says to review
    info_texts = " ".join(i.value for i in at.info)
    assert "Review the job description" in info_texts
    # fit panel shows the banded result
    assert any("match" in m.value for m in at.metric)
    assert not at.exception


def test_status_transition_button_click_walks_state_machine(temp_db):
    at = _open_opportunities(_run_app())
    # DISCOVERED allows REVIEWED / WITHDRAWN / CLOSED - click REVIEWED
    reviewed = [b for b in at.button if b.label == "REVIEWED"]
    assert reviewed, f"expected a REVIEWED transition button, got {[b.label for b in at.button]}"
    reviewed[0].click().run()
    assert not at.exception, f"exception after transition: {at.exception}"
    # the store now shows REVIEWED with a 2-event history
    app = temp_db["apps"].get(temp_db["app"].application_id)
    assert app.current_state == "REVIEWED"
    events = temp_db["apps"].events(app.application_id)
    assert [e.new_state for e in events] == ["DISCOVERED", "REVIEWED"]
    assert events[1].trigger == "user:workspace-button"
    assert events[1].provenance == "opportunities workspace"


def test_evidence_library_page_lists_seeded_evidence(temp_db):
    at = _open_opportunities(_run_app())
    at.radio[0].set_value("Evidence Library").run()
    assert not at.exception, f"exception on Evidence Library: {at.exception}"
    markdown = " ".join(m.value for m in at.markdown)
    assert "[E1]" in markdown
    assert "Data Engineer" in markdown  # the seeded item title
