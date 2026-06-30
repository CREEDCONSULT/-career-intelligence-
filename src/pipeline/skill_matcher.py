"""Fast, single-pass skill extraction via flashtext2 (word-boundary aware).

Replaces the previous per-n-gram fuzzy match (O(postings x ngrams x 34k)),
which was far too slow and over-matched. flashtext scans each text once and
only matches whole tokens/phrases, so "r" never matches inside "communicator".
"""
from __future__ import annotations

from flashtext2 import KeywordProcessor


class SkillMatcher:
    def __init__(self, name_to_id: dict[str, str]):
        """``name_to_id`` maps lowercase skill name/synonym -> skill_id."""
        self.kp = KeywordProcessor(case_sensitive=False)
        self.id_to_name: dict[str, str] = {}
        for name, skill_id in name_to_id.items():
            n = (name or "").strip()
            if len(n) < 2:  # skip 1-char skills to avoid noise
                continue
            self.kp.add_keyword(n, skill_id)
            self.id_to_name.setdefault(skill_id, n)

    def extract(self, text: str) -> list[dict]:
        if not text:
            return []
        seen: set[str] = set()
        out: list[dict] = []
        for skill_id in self.kp.extract_keywords(text):
            if skill_id in seen:
                continue
            seen.add(skill_id)
            out.append({"skill_id": skill_id, "skill_name": self.id_to_name.get(skill_id, skill_id)})
        return out
