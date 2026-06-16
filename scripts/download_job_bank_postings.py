#!/usr/bin/env python3
"""
Download Job Bank Open Data monthly postings CSVs.
Filters for Toronto/GTA locations.
Source: https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072
"""
import os
import re
import sys
import time
import requests
from pathlib import Path
from tqdm import tqdm
from urllib.parse import urljoin

BASE_URL = "https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "job_bank_postings"

# Toronto/GTA location filters (case-insensitive)
TORONTO_LOCATIONS = [
    "toronto", "mississauga", "brampton", "vaughan", "markham",
    "richmond hill", "oakville", "burlington", "milton", "halton hills",
    "ajax", "pickering", "whitby", "oshawa", "clarington",
    "scarborough", "north york", "etobicoke", "east york", "york",
    "guelph", "waterloo", "kitchener", "cambridge", "hamilton",
    "niagara", "st. catharines", "thorold", "welland"
]

def get_resource_urls():
    """Scrape the dataset page for monthly CSV resource URLs."""
    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    
    # Find all resource links ending in .csv
    csv_links = re.findall(r'href="(/data/dataset/[^"]+\.csv)"', resp.text)
    
    urls = []
    for link in csv_links:
        full_url = urljoin("https://open.canada.ca", link)
        if "/download/" in full_url:
            urls.append(full_url)
    
    return urls

def filter_toronto_rows(input_path, output_path):
    """Filter CSV for Toronto/GTA locations."""
    import pandas as pd
    
    df = pd.read_csv(input_path, low_memory=False)
    
    # Find location column (varies by file)
    location_cols = [c for c in df.columns if 'location' in c.lower() or 'work' in c.lower()]
    if not location_cols:
        return 0
    
    loc_col = location_cols[0]
    mask = df[loc_col].astype(str).str.lower().apply(
        lambda x: any(loc in x for loc in TORONTO_LOCATIONS)
    )
    
    filtered = df[mask]
    filtered.to_csv(output_path, index=False)
    return len(filtered)

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Fetching resource URLs...")
    urls = get_resource_urls()
    print(f"Found {len(urls)} CSV resources")
    
    total_rows = 0
    for url in tqdm(urls, desc="Downloading"):
        filename = url.split("/")[-1]
        raw_path = RAW_DIR / filename
        filtered_path = RAW_DIR / f"toronto_{filename}"
        
        # Download with retries
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                with open(raw_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"Failed after 3 attempts: {url} - {e}")
                    continue
                time.sleep(2 ** attempt)
        
        # Filter for Toronto
        try:
            count = filter_toronto_rows(raw_path, filtered_path)
            if count > 0:
                print(f"  {filename}: {count} Toronto rows")
                total_rows += count
        except Exception as e:
            print(f"  Filter error for {filename}: {e}")
    
    print(f"\nTotal Toronto/GTA rows across all files: {total_rows:,}")

if __name__ == "__main__":
    main()
