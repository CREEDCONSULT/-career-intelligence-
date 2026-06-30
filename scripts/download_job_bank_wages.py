#!/usr/bin/env python3
"""
Download Job Bank Wages annual CSVs via the open.canada.ca CKAN API.
Filters for the Toronto economic region.

Source dataset: adad580f-76b0-4502-bd05-20c125de9116 (annual files 2012-2025)
"""
import argparse
from pathlib import Path

from pipeline.io_utils import ckan_csv_resources, http_get, read_csv_bytes

DATASET_ID = "adad580f-76b0-4502-bd05-20c125de9116"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "job_bank_wages"
TORONTO_ER_CODES = {"3530", "ER3530"}


def _col(df, *needles):
    for c in df.columns:
        norm = " ".join(str(c).lower().split())
        for n in needles:
            if n in norm:
                return c
    return None


def filter_toronto(df):
    name_col = _col(df, "er_name", "economic region name", "er name")
    code_col = _col(df, "er_code", "economic region code", "er code")
    mask = None
    if name_col is not None:
        mask = df[name_col].fillna("").astype(str).str.contains("toronto", case=False, na=False)
    if code_col is not None:
        code_mask = df[code_col].fillna("").astype(str).str.replace(".0", "", regex=False).str.strip().isin(TORONTO_ER_CODES)
        mask = code_mask if mask is None else (mask | code_mask)
    if mask is None:
        raise ValueError(f"No economic-region column in {list(df.columns)[:10]}")
    return df[mask]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3, help="how many most-recent annual files")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    resources = ckan_csv_resources(DATASET_ID, "en")
    if not resources:
        raise SystemExit("No English CSV resources returned by CKAN")
    resources = resources[: args.years]
    print(f"Fetching {len(resources)} annual wage files...")

    grand_total = 0
    for r in resources:
        url = r["url"]
        fname = url.split("/")[-1]
        print(f"  - {r.get('name', fname)[:40]}")
        raw = http_get(url).content
        df = read_csv_bytes(raw)
        toronto = filter_toronto(df)
        assert len(toronto) > 0, f"No Toronto wage rows in {fname} (got {len(df)} total)"
        out_path = RAW_DIR / f"toronto_{fname}"
        toronto.to_csv(out_path, index=False, encoding="utf-8")
        print(f"      {len(toronto):,} Toronto rows / {len(df):,} total -> {out_path.name}")
        grand_total += len(toronto)

    print(f"\nTotal Toronto wage records: {grand_total:,}")


if __name__ == "__main__":
    main()
