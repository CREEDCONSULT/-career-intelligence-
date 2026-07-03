from llm.grounding import verify


def _judge(faithfulness_payload, rewrite_text):
    """Fake judge: returns claim JSON for the fact-check prompt, prose for the rewrite prompt."""
    def judge(prompt: str) -> str:
        if "fact-checker" in prompt.lower():
            import json
            return json.dumps(faithfulness_payload)
        return rewrite_text
    return judge


def test_verify_passes_through_faithful_prose():
    judge = _judge({"claims": [{"claim": "a", "supported": True}]}, "REWRITTEN")
    out = verify("original prose", "context", judge, threshold=0.9)
    assert out == "original prose"


def test_verify_rewrites_unfaithful_prose():
    judge = _judge({"claims": [{"claim": "a", "supported": False}]}, "REWRITTEN safely")
    out = verify("hallucinated prose", "context", judge, threshold=0.9)
    assert out == "REWRITTEN safely"
