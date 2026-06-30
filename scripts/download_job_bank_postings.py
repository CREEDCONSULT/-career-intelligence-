#!/usr/bin/env python3
"""
Download Job Bank Open Data monthly postings via the open.canada.ca CKAN API.
Filters each monthly CSV for Toronto/GTA locations and saves the filtered slice.

Source dataset: ea639e28-c0fc-48bf-b5dd-b8899bd43072
The monthly CSVs are UTF-16 LE, TAB-delimited (handled by io_utils.read_csv_bytes).
There is NO job-requirements free-text field; the richest text is the job title +
NOC21 Code Name (used downstream for skill extraction).
"""
import argparse
from pathlib import Path

from pipeline.io_utils import ckan_csv_resources, http_get, read_csv_bytes

DATASET_ID = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "job_bank_postings"

# Toronto/GTA location filters (case-insensitive substring match on the City column)
TORONTO_LOCATIONS = [
    "toronto", "mississauga", "brampton", "vaughan", "markham",
    "richmond hill", "oakville", "burlington", "milton", "halton hills",
    "ajax", "pickering", "whitby", "oshawa", "clarington",
    "scarborough", "north york", "etobicoke", "east york", "york",
]


def _col(df, *needles):
    """Find the first column whose normalized name matches any needle."""
    for c in df.columns:
        norm = " ".join(str(c).lower().split())  # collapse double spaces
        for n in needles:
            if n in norm:
                return c
    return None


def filter_toronto(df):
    city_col = _col(df, "city")
    er_col = _col(df, "economic region")
    if city_col is None and er_col is None:
        raise ValueError(f"No city/economic-region column found in {list(df.columns)[:8]}")
    mask = None
    if city_col is not None:
        city_lc = df[city_col].fillna("").astype(str).str.lower()
        mask = city_lc.apply(lambda x: any(loc in x for loc in TORONTO_LOCATIONS))
    if er_col is not None:
        er_mask = df[er_col].fillna("").astype(str).str.contains("toronto", case=False, na=False)
        mask = er_mask if mask is None else (mask | er_mask)
    return df[mask]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=6, help="how many most-recent months to fetch")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    resources = ckan_csv_resources(DATASET_ID, "en")
    if not resources:
        raise SystemExit("No English CSV resources returned by CKAN")
    # CKAN returns resources newest-first; take the requested window.
    resources = resources[: args.months]
    print(f"Fetching {len(resources)} monthly posting files...")

    grand_total = 0
    for r in resources:
        url = r["url"]
        fname = url.split("/")[-1]
        print(f"  - {r.get('name', fname)[:50]}")
        raw = http_get(url).content
        df = read_csv_bytes(raw)
        toronto = filter_toronto(df)
        assert len(toronto) > 0, f"No Toronto rows in {fname} (got {len(df)} total)"
        out_path = RAW_DIR / f"toronto_{fname}"
        toronto.to_csv(out_path, index=False, encoding="utf-8")
        print(f"      {len(toronto):,} Toronto rows / {len(df):,} total -> {out_path.name}")
        grand_total += len(toronto)

    print(f"\nTotal Toronto/GTA postings: {grand_total:,}")


if __name__ == "__main__":
    main()
