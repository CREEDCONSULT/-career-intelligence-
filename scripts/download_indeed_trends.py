#!/usr/bin/env python3
"""
Download Indeed Hiring Lab trend CSVs from GitHub.
Sources: Job postings index, wage tracker, AI tracker.
"""
import requests
import pandas as pd
from pathlib import Path
from io import StringIO

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "indeed"

INDEED_BASE = "https://raw.githubusercontent.com/hiring-lab"

FILES = {
    "job_postings_provincial": f"{INDEED_BASE}/job_postings_tracker/main/CA/provincial_postings_ca.csv",
    "job_postings_sectoral": f"{INDEED_BASE}/job_postings_tracker/main/CA/job_postings_by_sector_ca.csv",
    "wage_tracker": f"{INDEED_BASE}/indeed-wage-tracker/main/wage_tracker.csv",
    "ai_tracker": f"{INDEED_BASE}/ai-tracker/main/ai_tracker.csv",
    "remote_tracker": f"{INDEED_BASE}/remote-tracker/main/remote_tracker.csv",
}

def download_csv(url, name):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    for name, url in FILES.items():
        try:
            print(f"Downloading {name}...")
            df = download_csv(url, name)
            
            # Filter Ontario if geography column exists
            geo_cols = [c for c in df.columns if 'geograph' in c.lower() or 'region' in c.lower() or 'province' in c.lower()]
            if geo_cols:
                geo_col = geo_cols[0]
                ontario_mask = df[geo_col].astype(str).str.contains('Ontario|ON', case=False, na=False)
                df = df[ontario_mask]
            
            output_path = RAW_DIR / f"indeed_{name}.csv"
            df.to_csv(output_path, index=False)
            print(f"  Saved {len(df):,} rows to {output_path}")
        except Exception as e:
            print(f"  Error downloading {name}: {e}")

if __name__ == "__main__":
    main()
