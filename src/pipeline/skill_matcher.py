"""Fast, single-pass skill extraction via flashtext2 (word-boundary aware).

Replaces the previous per-n-gram fuzzy match (O(postings x ngrams x 34k)),
which was far too slow and over-matched. flashtext scans each text once and
only matches whole tokens/phrases, so "r" never matches inside "communicator".
"""
from __future__ import annotations

from flashtext2 import KeywordProcessor


def build_skill_index():
    """Build the canonical skill index shared by extraction and role-fit.

    Returns (name_to_id, cat_by_id, name_by_id). Combines the Lightcast taxonomy
    (exact lowercased names) with curated synonyms/acronyms; curated canonical
    names resolve to a Lightcast id when present, else a stable ``LOCAL:<name>`` id.
    """
    from pipeline.skill_synonyms import CURATED_SKILLS
    from pipeline.skill_taxonomy import get_taxonomy

    tax = get_taxonomy()
    name_to_id = {name: skill["id"] for name, skill in tax.by_name.items()}
    cat_by_id = {skill["id"]: skill.get("category", "") for skill in tax.skills.values()}
    for syn, canonical in CURATED_SKILLS.items():
        cid = name_to_id.get(canonical.lower())
        if not cid:
            cid = f"LOCAL:{canonical}"
            cat_by_id.setdefault(cid, "Specialized Skill")
        name_to_id[syn] = cid
        cat_by_id.setdefault(cid, "Specialized Skill")
    name_by_id: dict[str, str] = {}
    for nm, sid in name_to_id.items():
        if sid.startswith("LOCAL:"):
            name_by_id[sid] = sid.split(":", 1)[1]
        else:
            name_by_id.setdefault(sid, tax.skills.get(sid, {}).get("name", nm))
    return name_to_id, cat_by_id, name_by_id


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
