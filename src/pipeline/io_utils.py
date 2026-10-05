"""Shared HTTP + CSV helpers for the data pipeline.

All network access goes through ``http_get`` (retry + browser-ish UA).
``detect_encoding_sep`` / ``read_csv_bytes`` transparently handle the
Job Bank postings files, which are UTF-16 LE and TAB-delimited, as well as
the UTF-8(-BOM) comma files from StatsCan / wages.
"""
from __future__ import annotations

import io
import time

import pandas as pd
import requests

UA = {
    "User-Agent": "Mozilla/5.0 CareerIntelligenceDashboard/1.0",
    "Accept": "*/*",
}


def http_get(url: str, timeout: int = 90, retries: int = 3, stream: bool = False) -> requests.Response:
    """GET with simple linear backoff. Raises the last error after ``retries``."""
    last: Exception | None = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, stream=stream)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001 - re-raised after retries
            last = e
            time.sleep(1.5 * (i + 1))
    assert last is not None
    raise last


def detect_encoding_sep(raw: bytes) -> tuple[str, str]:
    """Sniff encoding (BOM-based) and delimiter (tab vs comma) from raw bytes."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif raw[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
        enc = "utf-8"
    head = raw[:4000].decode(enc, errors="replace")
    lines = head.splitlines()
    first = lines[0] if lines else ""
    sep = "\t" if first.count("\t") > first.count(",") else ","
    return enc, sep


def read_csv_bytes(raw: bytes, **kw) -> pd.DataFrame:
    """Parse CSV bytes with auto-detected encoding and separator."""
    enc, sep = detect_encoding_sep(raw)
    return pd.read_csv(io.BytesIO(raw), encoding=enc, sep=sep, low_memory=False, **kw)


def ckan_csv_resources(dataset_id: str, lang: str = "en") -> list[dict]:
    """Return open.canada.ca CKAN resources that are downloadable CSVs in ``lang``."""
    url = f"https://open.canada.ca/data/api/action/package_show?id={dataset_id}"
    data = http_get(url).json()
    out: list[dict] = []
    for r in data["result"]["resources"]:
        u = (r.get("url") or "")
        langs = r.get("language") or ["en"]
        if u.lower().endswith(".csv") and lang in langs:
            out.append(r)
    return out
