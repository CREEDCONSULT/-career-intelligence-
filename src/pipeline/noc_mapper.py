"""
NOC 2021 code mapper.
Loads the official Statistics Canada NOC 2021 V1.0 classification structure
(code -> readable title) for joining across datasets.

Source CSV (UTF-8 BOM, comma):
https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/noc-2021-v1.0-classification-structure.csv
Columns: Level, Hierarchical structure, Code - NOC 2021 V1.0, Class title, Class definition
"""
import re
from pathlib import Path

import pandas as pd

from pipeline.io_utils import http_get, read_csv_bytes

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
NOC_CSV_URL = (
    "https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/"
    "noc-2021-v1.0-classification-structure.csv"
)


def normalize_noc(code) -> str:
    """Normalize any NOC representation to a digits-only key, left-padded to 5.

    Handles ``NOC_21231`` (wages), ``21231.0`` (float-cast), ints, and blanks.
    Codes shorter than 5 digits (broad/major groups) are left-padded.
    """
    if code is None:
        return ""
    s = str(code).strip()
    if "." in s:  # drop float suffix like "21231.0"
        s = s.split(".", 1)[0]
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    return digits.zfill(5) if len(digits) < 5 else digits


class NOCMapper:
    def __init__(self):
        self.noc_to_title = {}
        self.noc_to_category = {}
        self._load()

    def _load(self):
        cache_file = CACHE_DIR / "noc_2021.csv"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if cache_file.exists():
                df = pd.read_csv(cache_file, dtype=str)
            else:
                raw = http_get(NOC_CSV_URL).content
                df = read_csv_bytes(raw, dtype=str)
                df.to_csv(cache_file, index=False, encoding="utf-8")
        except Exception as e:  # noqa: BLE001 - network/parse fallback
            print(f"NOC download failed ({e}); using minimal fallback map.")
            self._load_fallback()
            return

        code_col = next((c for c in df.columns if "code" in c.lower()), None)
        title_col = next((c for c in df.columns if "title" in c.lower()), None)
        level_col = next((c for c in df.columns if "level" in c.lower()), None)
        if code_col is None or title_col is None:
            self._load_fallback()
            return

        broad = {}  # first digit -> broad category title (Level 1 rows)
        for _, row in df.iterrows():
            raw_code = str(row.get(code_col, "")).strip()
            title = str(row.get(title_col, "")).strip()
            if not raw_code or raw_code.lower() == "nan":
                continue
            self.noc_to_title[raw_code] = title
            # also index the zero-padded 5-digit form for join robustness
            self.noc_to_title.setdefault(normalize_noc(raw_code), title)
            lvl = str(row.get(level_col, "")).strip() if level_col else ""
            if lvl in ("1", "Broad Category", "Broad category") and len(re.sub(r"\D", "", raw_code)) == 1:
                broad[re.sub(r"\D", "", raw_code)] = title

        # category = broad category by first digit of the code
        for code, title in list(self.noc_to_title.items()):
            d = re.sub(r"\D", "", code)
            self.noc_to_category[code] = broad.get(d[0], "Unknown") if d else "Unknown"

    def _load_fallback(self):
        """Minimal fallback for common Toronto NOCs (used only if download fails)."""
        self.noc_to_title = {
            "21211": "Data scientists",
            "21220": "Cybersecurity specialists",
            "21221": "User experience designers",
            "21222": "Information systems specialists",
            "21223": "Database analysts and data administrators",
            "21230": "Computer systems developers and programmers",
            "21231": "Software engineers and designers",
            "21232": "Software developers and programmers",
            "21233": "Web designers",
            "21234": "Web developers and programmers",
            "11200": "Human resources professionals",
            "11201": "Professional occupations in business management consulting",
            "11202": "Professional occupations in advertising, marketing and public relations",
            "10010": "Financial managers",
            "12010": "Supervisors, general office and administrative support workers",
            "13100": "Administrative officers",
        }
        self.noc_to_category = {k: "Business, finance and administration / Technology" for k in self.noc_to_title}

    def get_title(self, noc_code):
        key = str(noc_code).strip()
        if key in self.noc_to_title:
            return self.noc_to_title[key]
        norm = normalize_noc(noc_code)
        return self.noc_to_title.get(norm, key)

    def get_category(self, noc_code):
        key = str(noc_code).strip()
        if key in self.noc_to_category:
            return self.noc_to_category[key]
        return self.noc_to_category.get(normalize_noc(noc_code), "Unknown")
