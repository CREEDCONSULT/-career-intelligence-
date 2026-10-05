import pytest

from llm.config import LLMConfig
from llm.gateway import BudgetExceeded, Gateway


def _fake_completion_factory(total_tokens=15, content="hi"):
    def fake_completion(**kw):
        fake_completion.last_kwargs = kw
        msg = type("Msg", (), {"content": content})()
        choice = type("Choice", (), {"message": msg})()
        usage = type("Usage", (), {
            "prompt_tokens": 10,
            "completion_tokens": max(total_tokens - 10, 0),
            "total_tokens": total_tokens,
        })()
        return type("Resp", (), {"choices": [choice], "usage": usage})()
    return fake_completion


def test_gateway_returns_text_and_tracks_tokens():
    cfg = LLMConfig(provider="anthropic", models={"interactive": "m", "batch": "m", "hard": "m"}, token_budget=100)
    gw = Gateway(cfg, completion_fn=_fake_completion_factory())
    out = gw.complete([{"role": "user", "content": "x"}], tier="interactive")
    assert out.text == "hi"
    assert out.tokens == 15
    assert gw.tokens_used == 15


def test_gateway_enforces_budget():
    cfg = LLMConfig(provider="anthropic", models={"interactive": "m"}, token_budget=10)
    gw = Gateway(cfg, completion_fn=_fake_completion_factory(total_tokens=15))
    gw.complete([{"role": "user", "content": "x"}], tier="interactive")  # 15 > 10 after first call
    with pytest.raises(BudgetExceeded):
        gw.complete([{"role": "user", "content": "y"}], tier="interactive")


def test_gateway_routes_correct_model():
    cfg = LLMConfig(provider="anthropic", models={"interactive": "model-i", "batch": "model-b", "hard": "h"}, token_budget=1000)
    fake = _fake_completion_factory()
    gw = Gateway(cfg, completion_fn=fake)
    gw.complete([{"role": "user", "content": "x"}], tier="batch")
    assert fake.last_kwargs["model"] == "model-b"


def test_gateway_uses_cache(tmp_path):
    from llm.cache import ResponseCache
    cfg = LLMConfig(provider="anthropic", models={"interactive": "m"}, token_budget=1000)
    cache = ResponseCache(tmp_path / "c.duckdb")
    calls = {"n": 0}

    def counting_completion(**kw):
        calls["n"] += 1
        return _fake_completion_factory(content="cached!")(**kw)

    gw = Gateway(cfg, completion_fn=counting_completion, cache=cache)
    a = gw.complete([{"role": "user", "content": "same"}], tier="interactive")
    b = gw.complete([{"role": "user", "content": "same"}], tier="interactive")
    assert a.text == b.text == "cached!"
    assert calls["n"] == 1  # second call served from cache
