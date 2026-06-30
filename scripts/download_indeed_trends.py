#!/usr/bin/env python3
"""
Download Indeed Hiring Lab trend CSVs from GitHub (verified paths).

job_postings_tracker uses the `master` branch; metro file carries Toronto, ON.
wage + ai trackers are tried on `main` then `master`.
"""
import io
from pathlib import Path

import pandas as pd

from pipeline.io_utils import http_get

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "indeed"

# (key, [candidate urls in priority order])
SOURCES = {
    "metro_postings": [
        "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/metro_job_postings_CA.csv",
    ],
    "provincial_postings": [
        "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/provincial_postings_ca.csv",
    ],
    "sector_postings": [
        "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/CA/job_postings_by_sector_CA.csv",
    ],
    "wage_by_country": [
        "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/main/posted-wage-growth-by-country.csv",
        "https://raw.githubusercontent.com/hiring-lab/indeed-wage-tracker/master/posted-wage-growth-by-country.csv",
    ],
    "ai_postings": [
        "https://raw.githubusercontent.com/hiring-lab/ai-tracker/main/AI_posting.csv",
        "https://raw.githubusercontent.com/hiring-lab/ai-tracker/master/AI_posting.csv",
    ],
}


def fetch_first(urls):
    last = None
    for u in urls:
        try:
            raw = http_get(u, retries=2).content
            return pd.read_csv(io.BytesIO(raw)), u
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for key, urls in SOURCES.items():
        try:
            df, used = fetch_first(urls)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {key}: all candidates failed ({e})")
            continue

        # Geographic narrowing where the file is national.
        if key == "metro_postings":
            metro_col = next((c for c in df.columns if c.lower() == "metro"), None)
            if metro_col:
                df = df[df[metro_col].astype(str).str.contains("Toronto", case=False, na=False)]
            assert len(df) > 0, "No Toronto rows in Indeed metro file"
        elif key == "provincial_postings":
            prov_col = next((c for c in df.columns if "province" in c.lower()), None)
            if prov_col:
                df = df[df[prov_col].astype(str).str.lower().isin(["on", "ontario"])]

        out_path = RAW_DIR / f"indeed_{key}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")
        print(f"  {key}: {len(df):,} rows -> {out_path.name}  ({used.split('/')[-1]})")


if __name__ == "__main__":
    main()
