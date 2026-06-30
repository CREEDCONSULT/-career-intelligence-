#!/usr/bin/env python3
"""
Download StatsCan Job Vacancies (Table 14-10-0444-01) via the WDS REST API,
filtered for the Toronto economic region.

NOTE: ``www150.statcan.gc.ca`` is blocked from some egress environments
(e.g. this build sandbox returns WinError 10054). It works from a normal
Canadian connection. This downloader is therefore *optional*: on any network
failure it prints a skip message and exits 0 so the pipeline continues using
Indeed's Toronto metro data as the primary market-context source.
"""
import argparse
import io
import sys
import zipfile

import pandas as pd

from pipeline.io_utils import http_get

TABLE_ID = "14100444"
RAW_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "raw" / "statscan"


def download_table_csv() -> pd.DataFrame:
    url = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{TABLE_ID}/en"
    meta = http_get(url, retries=3).json()
    download_url = meta.get("object")
    if not download_url:
        raise ValueError(f"No download URL in WDS response: {meta}")
    zip_bytes = http_get(download_url, retries=3, timeout=180).content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv") and "MetaData" not in n)
        with z.open(csv_name) as f:
            return pd.read_csv(f, low_memory=False)


def filter_toronto(df: pd.DataFrame) -> pd.DataFrame:
    geo_col = next((c for c in df.columns if c.upper() == "GEO" or "geo" in c.lower()), None)
    if geo_col is None:
        return df
    return df[df[geo_col].fillna("").astype(str).str.contains("Toronto", case=False, na=False)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-skip", action="store_true", default=True,
                    help="exit 0 on network failure (default) instead of erroring")
    ap.add_argument("--require", dest="allow_skip", action="store_false",
                    help="fail hard if StatsCan is unreachable")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        print(f"Downloading StatsCan JVWS table {TABLE_ID}...")
        df = download_table_csv()
        toronto = filter_toronto(df)
        out = RAW_DIR / "jvws_toronto.csv"
        toronto.to_csv(out, index=False, encoding="utf-8")
        print(f"  Toronto rows: {len(toronto):,} / {len(df):,} -> {out.name}")
    except Exception as e:  # noqa: BLE001
        msg = f"StatsCan JVWS unavailable here ({type(e).__name__}: {e})."
        if args.allow_skip:
            print(f"  ! {msg} Skipping (run from a Canadian connection to include it).")
            sys.exit(0)
        raise


if __name__ == "__main__":
    main()
