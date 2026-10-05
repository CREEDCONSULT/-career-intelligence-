"""Dev helper: capture dashboard screenshots for docs (not part of the pipeline)."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8534"

PAGES = [
    ("Skill Demand", "skill_demand"),
    ("Salary Ranges", "salary_ranges"),
    ("Role Fit", "role_fit"),
    ("Market Context", "market_context"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1024})
    page.goto(BASE, wait_until="networkidle")
    time.sleep(4)
    for label, fname in PAGES:
        try:
            page.get_by_text(label, exact=False).first.click()
            time.sleep(4)  # let plotly render
        except Exception as e:
            print(f"  nav {label} failed: {e}")
        page.screenshot(path=str(OUT / f"{fname}.png"), full_page=True)
        print(f"  saved {fname}.png")
    browser.close()
print("done")
