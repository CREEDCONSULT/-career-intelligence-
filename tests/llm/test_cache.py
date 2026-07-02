from llm.cache import ResponseCache


def test_cache_roundtrip(tmp_path):
    c = ResponseCache(tmp_path / "cache.duckdb")
    key = c.key("anthropic/claude", "prompt text")
    assert c.get(key) is None
    c.put(key, "the response", tokens=42)
    assert c.get(key) == "the response"


def test_key_is_stable_and_content_addressed(tmp_path):
    c = ResponseCache(tmp_path / "cache.duckdb")
    assert c.key("m", "abc") == c.key("m", "abc")
    assert c.key("m", "abc") != c.key("m", "abd")
    assert c.key("m1", "abc") != c.key("m2", "abc")


def test_put_is_idempotent(tmp_path):
    c = ResponseCache(tmp_path / "cache.duckdb")
    k = c.key("m", "p")
    c.put(k, "v1", tokens=1)
    c.put(k, "v2", tokens=2)
    assert c.get(k) == "v2"
