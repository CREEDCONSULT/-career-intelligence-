from llm.config import LLMConfig


def test_defaults_to_anthropic_tiers(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_MODEL_BATCH", "LLM_MODEL_INTERACTIVE", "LLM_MODEL_HARD"):
        monkeypatch.delenv(k, raising=False)
    cfg = LLMConfig.from_env()
    assert cfg.provider == "anthropic"
    assert "haiku" in cfg.model_for("batch").lower()
    assert cfg.token_budget > 0


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL_INTERACTIVE", "openai/gpt-4o")
    cfg = LLMConfig.from_env()
    assert cfg.provider == "openai"
    assert cfg.model_for("interactive") == "openai/gpt-4o"


def test_unknown_tier_falls_back_to_interactive(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cfg = LLMConfig.from_env()
    assert cfg.model_for("nonsense") == cfg.model_for("interactive")
