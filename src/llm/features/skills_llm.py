"""Phase 3: LLM skill extraction from job titles (batch, structured, validated).

Research pattern: structured JSON extraction + Pydantic validation + a cheap batch
model (Haiku tier) + a cached shared instruction prefix. Titles are processed in
numbered batches; a malformed batch gets one retry, then is skipped (never crashes
the pipeline). This complements the flashtext dictionary matcher by surfacing
*implied* competencies a dictionary can't see (e.g. "Toddler Gymnastics Coach" →
childcare, safety, instruction).
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

INSTRUCTIONS = """You label job titles with the skills and competencies they imply.
For each numbered job title, list 2-6 concrete skills a hiring manager would expect.
Prefer canonical skill names (e.g. "Customer Service", "Food Preparation", "Python").
Categories: "Specialized Skill" (technical/domain), "Common Skill" (transferable), "Certification".
Respond with ONLY a JSON array, no prose:
[{"i": 1, "skills": [{"name": "...", "category": "..."}]}, {"i": 2, "skills": [...]}]
"""


class SkillItem(BaseModel):
    name: str
    category: str = "Specialized Skill"


def _parse(text: str) -> dict[int, list[SkillItem]]:
    m = _FENCE_RE.search(text or "")
    payload = (m.group(1) if m else text or "").strip()
    data = json.loads(payload)
    out: dict[int, list[SkillItem]] = {}
    for entry in data:
        idx = int(entry["i"])
        items = []
        for raw in entry.get("skills", []):
            try:
                item = SkillItem.model_validate(raw)
            except (ValidationError, TypeError):
                continue
            if item.name.strip():
                items.append(item)
        out[idx] = items
    return out


def extract_titles(titles: list[str], gw, batch_size: int = 25) -> dict[str, list[SkillItem]]:
    """Extract implied skills for each title. Returns {title: [SkillItem, ...]}."""
    results: dict[str, list[SkillItem]] = {t: [] for t in titles}
    for start in range(0, len(titles), batch_size):
        batch = titles[start:start + batch_size]
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(batch))
        for attempt in range(2):
            resp = gw.complete(
                [{"role": "user", "content": f"Job titles:\n{numbered}"}],
                tier="batch",
                cache_prefix=INSTRUCTIONS,
            )
            try:
                parsed = _parse(resp.text)
            except Exception:  # noqa: BLE001 - malformed batch, retry once
                continue
            for i, title in enumerate(batch):
                results[title] = parsed.get(i + 1, [])
            break
    return results
