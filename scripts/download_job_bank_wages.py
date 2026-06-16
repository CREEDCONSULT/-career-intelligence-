#!/usr/bin/env python3
"""
Download Job Bank Wages annual CSV.
Filters for Toronto economic region (3530).
Source: https://open.canada.ca/data/en/dataset/adad580f-76b0-4502-bd05-20c125de9116
"""
import os
import re
import requests
from pathlib import Path
from tqdm import tqdm

DATASET_URL = "https://open.canada.ca/data/en/dataset/adad580f-76b0-4502-bd05-20c125de9116"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "job_bank_wages"
TORONTO_ECONOMIC_REGION = "3530"  # Toronto

def get_wage_csv_url():
    """Get the annual wages CSV download URL."""
    resp = requests.get(DATASET_URL, timeout=30)
    resp.raise_for_status()
    
    # Find the CSV resource
    matches = re.findall(r'href="(/data/dataset/[^"]+\.csv)"', resp.text)
    for m in matches:
        if "/download/" in m:
            return "https://open.canada.ca" + m
    raise ValueError("No CSV download URL found")

def filter_toronto_wages(input_path, output_path):
    """Filter for Toronto economic region."""
    import pandas as pd
    
    df = pd.read_csv(input_path)
    
    # Find region column
    region_cols = [c for c in df.columns if 'region' in c.lower() or 'geo' in c.lower()]
    if not region_cols:
        return 0
    
    reg_col = region_cols[0]
    # Filter for Toronto (3530) - handle both string and numeric
    mask = df[reg_col].astype(str).str.strip() == TORONTO_ECONOMIC_REGION
    
    filtered = df[mask]
    filtered.to_csv(output_path, index=False)
    return len(filtered)

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Fetching wage CSV URL...")
    url = get_wage_csv_url()
    print(f"Downloading from: {url}")
    
    filename = "job_bank_wages.csv"
    raw_path = RAW_DIR / filename
    filtered_path = RAW_DIR / f"toronto_{filename}"
    
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(raw_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print("Filtering for Toronto economic region 3530...")
    count = filter_toronto_wages(raw_path, filtered_path)
    print(f"Toronto wage records: {count:,}")

if __name__ == "__main__":
    main()
