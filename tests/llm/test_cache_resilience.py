"""The response cache must never kill a paid LLM run: on persistent IO failure
(e.g. a cloud-sync agent locking the file) it disables itself and no-ops."""
import duckdb
import pytest

from llm.cache import ResponseCache


def test_cache_disables_on_connect_failure(monkeypatch, tmp_path):
    real_connect = duckdb.connect

    def failing_connect(*a, **kw):
        raise duckdb.IOException("file locked by another process")

    monkeypatch.setattr(duckdb, "connect", failing_connect)
    c = ResponseCache(tmp_path / "locked.duckdb", retries=1, retry_wait=0.0)
    assert c.disabled is True
    # no-ops, no exceptions
    assert c.get(c.key("m", "p")) is None
    c.put(c.key("m", "p"), "value", tokens=1)
    monkeypatch.setattr(duckdb, "connect", real_connect)


def test_cache_survives_transient_get_failure(monkeypatch, tmp_path):
    c = ResponseCache(tmp_path / "ok.duckdb", retries=1, retry_wait=0.0)
    k = c.key("m", "p")
    c.put(k, "v", tokens=1)

    def failing_connect(*a, **kw):
        raise duckdb.IOException("locked")

    monkeypatch.setattr(duckdb, "connect", failing_connect)
    # locked mid-run: get degrades to a miss instead of raising
    assert c.get(k) is None
    c.put(k, "v2", tokens=1)  # and put no-ops


def test_healthy_cache_still_roundtrips(tmp_path):
    c = ResponseCache(tmp_path / "h.duckdb", retries=2, retry_wait=0.0)
    assert c.disabled is False
    k = c.key("m", "p")
    c.put(k, "hello", tokens=5)
    assert c.get(k) == "hello"
