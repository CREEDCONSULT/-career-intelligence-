#!/usr/bin/env python3
"""Google OAuth authorization flow for Career Intelligence (M2.1).

Run ONCE on the founder's local machine to authorize read-only access to
Gmail, Calendar, and Drive. Opens a browser for Google consent.

Prerequisites (see CAREER_INTELLIGENCE_M2_1_GOOGLE_OPERATIONS_REPORT.md
for step-by-step instructions):
1. Google Cloud project with Gmail/Calendar/Drive APIs enabled
2. OAuth 2.0 credentials (Desktop app) downloaded to:
   data/processed/google_credentials.json
3. Your Google account added as a test user

Usage:
    python scripts/google_authorize.py           # full flow
    python scripts/google_authorize.py --revoke  # revoke + delete tokens
    python scripts/google_authorize.py --status  # check current health
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Google OAuth for Career Intelligence")
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--revoke", action="store_true", help="Revoke tokens at Google + delete local file"
    )
    group.add_argument("--status", action="store_true", help="Show connector health status")
    group.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local redirect port for the OAuth flow (default: 8080)",
    )
    args = ap.parse_args()

    from careeros import google_oauth

    if args.revoke:
        print("Revoking Google tokens...")
        if google_oauth.revoke_tokens():
            print("Tokens revoked at Google and local file deleted.")
            print("Confirm at: https://myaccount.google.com/permissions")
        else:
            print("No tokens found to revoke.")
        return 0

    if args.status:
        print("Checking Google connector health...")
        health = google_oauth.check_health()
        print(json.dumps(health.to_dict(), indent=2))
        for name, getter in [
            (
                "gmail",
                lambda: (
                    __import__("careeros.google_gmail", fromlist=["GmailConnector"])
                    .GmailConnector()
                    .health()
                ),
            ),
            (
                "calendar",
                lambda: (
                    __import__("careeros.google_calendar", fromlist=["CalendarConnector"])
                    .CalendarConnector()
                    .health()
                ),
            ),
            (
                "drive",
                lambda: (
                    __import__("careeros.google_drive", fromlist=["DriveConnector"])
                    .DriveConnector()
                    .health()
                ),
            ),
        ]:
            h = getter()
            print(json.dumps(h.to_dict(), indent=2))
        return 0

    # Default: run the authorization flow
    print("Starting Google OAuth authorization flow...")
    print()
    ok = google_oauth.run_authorization_flow(redirect_port=args.port)
    if ok:
        print()
        print("Next step: run the smoke test:")
        print("  python scripts/google_smoke_test.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
