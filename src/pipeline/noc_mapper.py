"""
NOC 2021 code mapper.
Loads NOC codes with readable titles for joining across datasets.
"""
import csv
import pandas as pd
import requests
from pathlib import Path
from io import StringIO

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
NOC_URL = "https://noc.esdc.gc.ca/api/noc/2021/v1.0/en/csv"  # Approximate

class NOCMapper:
    def __init__(self):
        self.noc_to_title = {}
        self.noc_to_category = {}
        self._load()
    
    def _load(self):
        cache_file = CACHE_DIR / "noc_2021.csv"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if cache_file.exists():
            df = pd.read_csv(cache_file)
        else:
            # Fallback: create minimal mapping from common NOCs
            self._load_fallback()
            return
        
        for _, row in df.iterrows():
            code = str(row.get("NOC_CODE", "")).strip()
            title = str(row.get("TITLE", "")).strip()
            category = str(row.get("BROAD_CATEGORY", "")).strip()
            if code:
                self.noc_to_title[code] = title
                self.noc_to_category[code] = category
    
    def _load_fallback(self):
        """Minimal fallback for common Toronto NOCs."""
        self.noc_to_title = {
            "21211": "Data scientists",
            "21210": "Mathematicians, statisticians and actuaries",
            "21220": "Cybersecurity specialists",
            "21221": "User experience designers",
            "21222": "Information systems specialists",
            "21223": "Database analysts and data administrators",
            "21230": "Computer systems developers and programmers",
            "21231": "Software engineers and designers",
            "21232": "Software testers",
            "21233": "Web designers and developers",
            "21234": "Web programmers",
            "11201": "Human resources professionals",
            "11202": "Business development officers",
            "11203": "Marketing specialists",
            "11200": "Financial auditors and accountants",
            "11100": "Financial analysts",
            "11101": "Financial and investment analysts",
            "11102": "Financial advisors",
            "11103": "Securities agents, investment dealers and brokers",
            "11109": "Other financial officers",
            "12101": "Human resources and recruitment officers",
            "12102": "Procurement and supply chain officers",
            "12200": "Accounting technicians and bookkeepers",
            "12201": "Insurance adjusters and claims examiners",
            "12202": "Banking, credit and other investment officers",
            "13100": "Administrative officers",
            "13101": "Executive assistants",
            "13102": "Court officers and justices of the peace",
            "14100": "General office support workers",
            "14101": "Receptionists",
            "14102": "Data entry clerks",
            "14103": "Desktop publishing operators",
            "14200": "Accounting and related clerks",
            "14201": "Payroll administrators",
            "14202": "Taxation and revenue clerks",
        }
        self.noc_to_category = {k: "Technology/Business" for k in self.noc_to_title}
    
    def get_title(self, noc_code):
        return self.noc_to_title.get(str(noc_code).strip(), noc_code)
    
    def get_category(self, noc_code):
        return self.noc_to_category.get(str(noc_code).strip(), "Unknown")
