import json

import pandas as pd

from llm.features.advisor import advise
from llm.features.ask import Answer
from llm.gateway import Response


class FakeGW:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages, tier="interactive", cache_prefix=None):
        return Response(text=self.responses.pop(0) if self.responses else "", tokens=1)


def _ask_stub(answer):
    def ask_fn(question, con, gw):
        return answer
    return ask_fn


def test_refuses_out_of_scope():
    gw = FakeGW(["OUT_OF_SCOPE"])
    adv = advise("What's the weather tomorrow?", con=None, gw=gw, ask_fn=_ask_stub(None))
    assert adv.refused is True
    assert adv.sources == []
    assert "can only" in adv.answer.lower() or "job market" in adv.answer.lower()


def test_happy_path_grounded_advice():
    table = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ans = Answer("top skills?", "SELECT ...", table, "Sales leads with 665.", True)
    gw = FakeGW([
        "What are the most in-demand skills?",                 # plan (1 query)
        "Sales leads demand with 665 postings — prioritise it.",  # compose
        json.dumps({"claims": [{"claim": "Sales 665", "supported": True}]}),  # faithfulness -> passes
    ])
    adv = advise("What skill should I learn?", con=None, gw=gw, ask_fn=_ask_stub(ans))
    assert adv.refused is False
    assert len(adv.sources) == 1
    assert "665" in adv.answer


def test_ungrounded_advice_is_regenerated():
    table = pd.DataFrame({"skill": ["Sales"], "postings": [665]})
    ans = Answer("top skills?", "SELECT ...", table, "Sales leads with 665.", True)
    gw = FakeGW([
        "What are the most in-demand skills?",   # plan
        "Sales had 999999 postings.",            # compose: invented number
        "Sales leads with 665 postings.",        # deterministic-regeneration compose
        json.dumps({"claims": [{"claim": "x", "supported": True}]}),  # faithfulness passes
    ])
    adv = advise("advise me", con=None, gw=gw, ask_fn=_ask_stub(ans))
    assert "999999" not in adv.answer
