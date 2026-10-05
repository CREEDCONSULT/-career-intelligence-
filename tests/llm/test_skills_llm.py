import json

from llm.features.skills_llm import extract_titles
from llm.gateway import Response


class FakeGW:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages, tier="batch", cache_prefix=None):
        self.calls += 1
        return Response(text=self.responses.pop(0), tokens=1)


def _payload(mapping):
    # mapping: {index: [(name, category), ...]}
    return json.dumps([
        {"i": i, "skills": [{"name": n, "category": c} for n, c in items]}
        for i, items in mapping.items()
    ])


def test_extracts_skills_per_title():
    gw = FakeGW([_payload({1: [("Cooking", "Specialized Skill")], 2: [("Sales", "Common Skill")]})])
    out = extract_titles(["Line Cook", "Sales Associate"], gw, batch_size=25)
    assert [s.name for s in out["Line Cook"]] == ["Cooking"]
    assert out["Sales Associate"][0].category == "Common Skill"


def test_handles_fenced_json():
    gw = FakeGW(["```json\n" + _payload({1: [("Python", "Specialized Skill")]}) + "\n```"])
    out = extract_titles(["Python Developer"], gw)
    assert out["Python Developer"][0].name == "Python"


def test_batches_and_retries_bad_batch_once():
    good = _payload({1: [("Welding", "Specialized Skill")]})
    gw = FakeGW(["THIS IS NOT JSON", good])  # first attempt fails, retry succeeds
    out = extract_titles(["Welder"], gw)
    assert gw.calls == 2
    assert out["Welder"][0].name == "Welding"


def test_skips_batch_after_two_failures():
    gw = FakeGW(["garbage", "still garbage"])
    out = extract_titles(["Mystery Job"], gw)
    assert out["Mystery Job"] == []


def test_drops_invalid_items_keeps_valid():
    raw = json.dumps([{"i": 1, "skills": [{"name": "Valid", "category": "Common Skill"},
                                          {"category": "missing name"}]}])
    gw = FakeGW([raw])
    out = extract_titles(["Job"], gw)
    assert [s.name for s in out["Job"]] == ["Valid"]
