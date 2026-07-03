import json

import pytest

from llm.grounding import faithfulness


def _judge_returning(payload):
    def judge(prompt: str) -> str:
        return json.dumps(payload)
    return judge


def test_faithfulness_all_supported():
    judge = _judge_returning({"claims": [
        {"claim": "Postings rose to 8000", "supported": True},
        {"claim": "Sales is the top skill", "supported": True},
    ]})
    assert faithfulness("...", "...", judge) == 1.0


def test_faithfulness_partial():
    judge = _judge_returning({"claims": [
        {"claim": "a", "supported": True},
        {"claim": "b", "supported": False},
    ]})
    assert faithfulness("...", "...", judge) == 0.5


def test_faithfulness_no_claims_is_perfect():
    judge = _judge_returning({"claims": []})
    assert faithfulness("...", "...", judge) == 1.0


def test_faithfulness_strips_fences():
    def judge(prompt: str) -> str:
        return '```json\n{"claims": [{"claim": "x", "supported": true}]}\n```'
    assert faithfulness("...", "...", judge) == 1.0


def test_faithfulness_raises_on_garbage():
    with pytest.raises(ValueError):
        faithfulness("...", "...", lambda p: "not json at all")
