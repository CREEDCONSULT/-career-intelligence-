"""
Lightcast Open Skills taxonomy loader.
Downloads and caches 34K+ skills for fuzzy matching.
"""
import json
import requests
from pathlib import Path
from functools import lru_cache

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
# Lightcast Open Skills (May 2023 snapshot mirror). Real Lightcast/EMSI skill IDs.
# Lightcast's official feed is an OAuth API; this static mirror avoids registration.
TAXONOMY_URL = "https://gist.githubusercontent.com/ThatGuySam/8a6e7bd152793ac12b7f60420d1017c8/raw"

class SkillTaxonomy:
    def __init__(self):
        self.skills = {}
        self.by_name = {}
        self.by_category = {}
        self._load()
    
    def _load(self):
        cache_file = CACHE_DIR / "lightcast_skills.json"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
        else:
            print("Downloading Lightcast Open Skills taxonomy...")
            resp = requests.get(TAXONOMY_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

        # The mirror is {"attributions": [...], "data": [ {id, name, type:{id,name}} ]}
        items = data["data"] if isinstance(data, dict) and "data" in data else data

        for raw in items:
            skill_id = raw.get("id", "")
            name = (raw.get("name") or "").lower().strip()
            category = (raw.get("type") or {}).get("name", "") if isinstance(raw.get("type"), dict) else (raw.get("category") or "")
            normalized = {
                "id": skill_id,
                "name": raw.get("name", ""),
                "category": category,
                "subcategory": raw.get("subcategory", ""),
            }
            if not skill_id or not name:
                continue
            self.skills[skill_id] = normalized
            self.by_name[name] = normalized
            if category:
                self.by_category.setdefault(category, []).append(skill_id)
    
    def get_skill(self, skill_id):
        return self.skills.get(skill_id)

@lru_cache(maxsize=1)
def get_taxonomy():
    return SkillTaxonomy()
