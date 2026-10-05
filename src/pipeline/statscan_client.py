"""
StatsCan WDS REST API client.
Provides typed access to Jobs data.
"""
import requests
import pandas as pd
from pathlib import Path
from typing import List
import io
import zipfile

BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

class StatsCanClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CareerIntelligenceDashboard/1.0"})
    
    def get_table_csv(self, table_id: str) -> pd.DataFrame:
        """Download full table as DataFrame."""
        cache_file = CACHE_DIR / f"statscan_{table_id}.csv"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if cache_file.exists():
            return pd.read_csv(cache_file)
        
        # Get download URL
        url = f"{BASE_URL}/getFullTableDownloadCSV/{table_id}/en"
        resp = self.session.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        
        download_url = data.get("object")
        if not download_url:
            raise ValueError(f"No download URL for table {table_id}")
        
        # Download and extract ZIP
        zip_resp = self.session.get(download_url, timeout=120, stream=True)
        zip_resp.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
            csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
            with z.open(csv_name) as csv_file:
                df = pd.read_csv(csv_file)
        
        df.to_csv(cache_file, index=False)
        return df
    
    def get_vectors_latest(self, vector_ids: List[str], periods: int = 12) -> pd.DataFrame:
        """Get latest N periods for specific vectors."""
        url = f"{BASE_URL}/getDataFromVectorsAndLatestNPeriods"
        payload = [{"vectorId": vid, "latestN": periods} for vid in vector_ids]
        
        resp = self.session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        records = []
        for item in data:
            vid = item.get("vectorId")
            for dp in item.get("dataPoints", []):
                records.append({
                    "vector_id": vid,
                    "date": dp.get("date"),
                    "value": dp.get("value"),
                    "status": dp.get("status", "A")
                })
        return pd.DataFrame(records)
    
    def get_table_metadata(self, table_id: str) -> dict:
        """Get table metadata including vector IDs."""
        url = f"{BASE_URL}/getCubeMetadata"
        payload = [{"productId": table_id}]
        
        resp = self.session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()[0]

# Convenience functions for our specific tables
def get_jvws_toronto() -> pd.DataFrame:
    """Get Job Vacancies (14-10-0444-01) filtered for Toronto."""
    client = StatsCanClient()
    df = client.get_table_csv("14100444")
    
    # Filter Toronto economic region
    geo_cols = [c for c in df.columns if 'GEO' in c.upper()]
    if geo_cols:
        geo_col = geo_cols[0]
        mask = df[geo_col].astype(str).str.contains("Toronto", case=False, na=False)
        return df[mask]
    return df

def get_lfs_toronto() -> pd.DataFrame:
    """Get Labour Force Survey (14-10-0459-01) for Toronto CMA."""
    client = StatsCanClient()
    df = client.get_table_csv("14100459")
    
    geo_cols = [c for c in df.columns if 'GEO' in c.upper()]
    if geo_cols:
        geo_col = geo_cols[0]
        mask = df[geo_col].astype(str).str.contains("Toronto", case=False, na=False)
        return df[mask]
    return df

if __name__ == "__main__":
    # Test
    print("Testing StatsCan client...")
    df = get_jvws_toronto()
    print(f"JVWS Toronto rows: {len(df)}")
    print(f"Columns: {list(df.columns)[:10]}")
