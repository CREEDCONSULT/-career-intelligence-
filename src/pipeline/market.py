"""Market configuration loader.

The whole pipeline + dashboard is parameterized on one market definition so a
second city ("want one for your market?") is a config change, not a rewrite.
Resolution order: $MARKET_CONFIG path -> repo config/market.yaml -> embedded
Toronto defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "market.yaml"

_TORONTO = {
    "name": "Toronto",
    "tagline": "Toronto job market, decoded.",
    "jobbank_cities": [
        "toronto", "mississauga", "brampton", "vaughan", "markham",
        "richmond hill", "oakville", "burlington", "milton", "halton hills",
        "ajax", "pickering", "whitby", "oshawa", "clarington",
        "scarborough", "north york", "etobicoke", "east york", "york",
    ],
    "economic_region_name": "Toronto",
    "economic_region_codes": ["3530", "ER3530"],
    "statscan_geo_contains": "Toronto",
    "indeed_metro": "Toronto, ON",
}


@dataclass(frozen=True)
class Market:
    name: str
    tagline: str
    jobbank_cities: list = field(default_factory=list)
    economic_region_name: str = ""
    economic_region_codes: list = field(default_factory=list)
    statscan_geo_contains: str = ""
    indeed_metro: str = ""


@lru_cache(maxsize=1)
def load_market() -> Market:
    path = Path(os.getenv("MARKET_CONFIG", str(_DEFAULT_PATH)))
    data = dict(_TORONTO)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        data.update({k: v for k, v in loaded.items() if v is not None})
    return Market(**{k: data[k] for k in Market.__dataclass_fields__})
