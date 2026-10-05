"""Live-model validation test (M2 1B).

Auto-skips without an LLM API key (this environment has none); activates in
any environment where a key is present so CI or a founder laptop completes
the live validation with zero extra setup. Validates the same evidence-citation
contract the deterministic fake-gateway tests assert, against the real provider:
cited IDs must exist in the ledger, excluded claims must stay out of the output,
and the result schema must be well-formed.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "streamlit_app"))

pytestmark = pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")),
    reason="live provider validation requires an LLM API key",
)


def test_live_tailor_validates_evidence_contract():
    from llm.cache import ResponseCache
    from llm.config import LLMConfig
    from llm.features.evidence_resume import tailor_evidence_based
    from llm.gateway import Gateway
    from scripts.validate_live_model import _build_fixture, _validate_contract

    cfg = LLMConfig.from_env()
    gw = Gateway(cfg, cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"))
    opportunity, evidence, base_resume = _build_fixture()
    valid_ids = {e.evidence_id for e in evidence if e.claims_allowed}

    result = tailor_evidence_based(base_resume, opportunity, evidence, gw)
    violations = _validate_contract(result, valid_ids, "tailor")
    assert not violations, violations
    assert result.model_used is True
    assert result.markdown.strip()


def test_live_cover_letter_validates_evidence_contract():
    from llm.cache import ResponseCache
    from llm.config import LLMConfig
    from llm.features.evidence_resume import cover_letter_evidence_based
    from llm.gateway import Gateway
    from scripts.validate_live_model import _build_fixture, _validate_contract

    cfg = LLMConfig.from_env()
    gw = Gateway(cfg, cache=ResponseCache(ROOT / "data" / "processed" / "llm_cache.duckdb"))
    opportunity, evidence, base_resume = _build_fixture()
    valid_ids = {e.evidence_id for e in evidence if e.claims_allowed}

    result = cover_letter_evidence_based(base_resume, opportunity, evidence, gw)
    violations = _validate_contract(result, valid_ids, "cover_letter")
    assert not violations, violations
    assert result.markdown.strip()


def test_live_output_uses_real_provider_config():
    from llm.config import LLMConfig

    cfg = LLMConfig.from_env()
    assert cfg.provider in ("anthropic", "openai")
    assert all(cfg.model_for(tier) for tier in ("batch", "interactive", "hard"))
