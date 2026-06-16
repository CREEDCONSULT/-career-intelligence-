#!/usr/bin/env python3
"""
Download StatsCan Job Vacancies (Table 14-10-0444-01) via WDS REST API.
Filters for Toronto economic region.
"""
import requests
import zipfile
import io
import pandas as pd
from pathlib import Path
from tqdm import tqdm

# StatsCan WDS REST API
BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
TABLE_ID = "14100444"  # 14-10-0444-01
TORONTO_ER = "Toronto"  # Economic region name
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "statscan"

def download_table_csv():
    """Download full table as CSV via WDS API."""
    url = f"{BASE_URL}/getFullTableDownloadCSV/{TABLE_ID}/en"
    
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    # The API returns a download URL
    download_url = data.get("object")
    if not download_url:
        raise ValueError("No download URL in response")
    
    # Download the ZIP
    zip_resp = requests.get(download_url, timeout=120, stream=True)
    zip_resp.raise_for_status()
    
    # Extract CSV from ZIP
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
        csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
        with z.open(csv_name) as csv_file:
            df = pd.read_csv(csv_file)
    
    return df

def filter_toronto(df):
    """Filter for Toronto economic region."""
    # Find GEO column
    geo_cols = [c for c in df.columns if 'GEO' in c.upper() or 'geo' in c.lower()]
    if not geo_cols:
        return pd.DataFrame()
    
    geo_col = geo_cols[0]
    mask = df[geo_col].astype(str).str.contains(TORONTO_ER, case=False, na=False)
    return df[mask]

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Downloading StatsCan JVWS table 14-10-0444-01...")
    df = download_table_csv()
    print(f"Total rows: {len(df):,}")
    
    print("Filtering for Toronto economic region...")
    toronto_df = filter_toronto(df)
    print(f"Toronto rows: {len(toronto_df):,}")
    
    if len(toronto_df) > 0:
        output_path = RAW_DIR / "jvws_toronto.csv"
        toronto_df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")
        
        # Show unique NOCs
        noc_cols = [c for c in toronto_df.columns if 'NOC' in c.upper()]
        if noc_cols:
            unique_nocs = toronto_df[noc_cols[0]].nunique()
            print(f"Unique NOC codes: {unique_nocs}")

if __name__ == "__main__":
    main()
