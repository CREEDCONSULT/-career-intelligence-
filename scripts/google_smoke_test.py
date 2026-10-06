#!/usr/bin/env python3
"""Google integration live smoke test (M2.1).

Run AFTER `python scripts/google_authorize.py` has completed successfully.
Exercises each connector against the real Google APIs with read-only
operations, verifies provenance, and reports results. NO secrets are
printed, committed, or logged.

Usage:
    python scripts/google_smoke_test.py
    python scripts/google_smoke_test.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report = {"gmail": {}, "calendar": {}, "drive": {}, "oauth": {}, "overall": "UNKNOWN"}

    # -- OAuth health ---------------------------------------------------------
    from careeros.google_oauth import check_health

    oauth_health = check_health()
    report["oauth"] = oauth_health.to_dict()
    if not oauth_health.authorized:
        report["overall"] = "BLOCKED"
        report["note"] = "Not authorized. Run scripts/google_authorize.py first."
        print(
            json.dumps(report, indent=2)
            if args.json
            else "Not authorized. Run scripts/google_authorize.py first."
        )
        return 1

    # -- Gmail -----------------------------------------------------------------
    from careeros.google_gmail import GmailConnector, CAREER_QUERIES

    gmail = GmailConnector()
    gh = gmail.health()
    report["gmail"] = gh.to_dict()

    if gh.authorized:
        # Read-only: search for career-relevant messages (bounded queries)
        results = []
        for signal_name, query in CAREER_QUERIES.items():
            threads = gmail.search_threads(query, limit=3)
            results.append(
                {
                    "signal": signal_name,
                    "threads_found": len(threads),
                    "sample_thread_ids": [t["thread_id"] for t in threads[:2]],
                }
            )
        report["gmail"]["smoke"] = {
            "queries_executed": len(CAREER_QUERIES),
            "results": results,
            "provenance_format": "gmail:thread/<thread_id>",
        }
        # Verify read-only enforcement
        try:
            gmail.send(type("M", (), {"to": "test", "subject": "t", "body": "b"})())
            report["gmail"]["error"] = "SEND NOT BLOCKED — SECURITY VIOLATION"
        except PermissionError:
            report["gmail"]["send_blocked"] = True

    # -- Calendar ---------------------------------------------------------------
    from careeros.google_calendar import CalendarConnector

    cal = CalendarConnector()
    ch = cal.health()
    report["calendar"] = ch.to_dict()

    if ch.authorized:
        events = cal.list_upcoming(within_days=14)
        relevant = cal.discover_interview_context(within_days=14)
        report["calendar"]["smoke"] = {
            "total_events_upcoming_14d": len(events),
            "interview_relevant": len(relevant),
            "sample": [e.to_dict() for e in relevant[:3]],
            "provenance_format": "gcal:event/<event_id>",
        }
        try:
            cal.create_event(type("E", (), {"title": "t", "start": None})())
            report["calendar"]["error"] = "CREATE NOT BLOCKED — SECURITY VIOLATION"
        except PermissionError:
            report["calendar"]["create_blocked"] = True

    # -- Drive -------------------------------------------------------------------
    from careeros.google_drive import DriveConnector

    drive = DriveConnector()
    dh = drive.health()
    report["drive"] = dh.to_dict()

    if dh.authorized:
        files = drive.list_files()
        artifacts = drive.discover_career_artifacts()
        relevant_files = [f for f in artifacts if f.relevant]
        report["drive"]["smoke"] = {
            "total_files_listed": len(files),
            "career_artifacts_found": len(relevant_files),
            "artifact_types": list(set(f.artifact_type for f in relevant_files)),
            "sample": [f.to_dict() for f in relevant_files[:5]],
            "provenance_format": "gdrive:file/<file_id>",
        }
        try:
            drive.upload(type("F", (), {"name": "t", "content": b"", "mime_type": "text/plain"})())
            report["drive"]["error"] = "UPLOAD NOT BLOCKED — SECURITY VIOLATION"
        except PermissionError:
            report["drive"]["upload_blocked"] = True

    # -- Overall verdict ----------------------------------------------------------
    all_live = all(
        [
            gh.authorized,
            ch.authorized,
            dh.authorized,
            report.get("gmail", {}).get("send_blocked", False),
            report.get("calendar", {}).get("create_blocked", False),
            report.get("drive", {}).get("upload_blocked", False),
        ]
    )
    report["overall"] = "PASS" if all_live else "PARTIAL"
    report["checks"] = {
        "gmail_authorized": gh.authorized,
        "calendar_authorized": ch.authorized,
        "drive_authorized": dh.authorized,
        "gmail_send_blocked": report.get("gmail", {}).get("send_blocked", False),
        "calendar_create_blocked": report.get("calendar", {}).get("create_blocked", False),
        "drive_upload_blocked": report.get("drive", {}).get("upload_blocked", False),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"OAuth: {report['oauth']['status']}")
        print(
            f"Gmail: {report['gmail'].get('status', 'N/A')} | "
            f"send blocked: {report['gmail'].get('send_blocked', 'N/A')}"
        )
        print(
            f"Calendar: {report['calendar'].get('status', 'N/A')} | "
            f"create blocked: {report['calendar'].get('create_blocked', 'N/A')}"
        )
        print(
            f"Drive: {report['drive'].get('status', 'N/A')} | "
            f"upload blocked: {report['drive'].get('upload_blocked', 'N/A')}"
        )
        print(f"Overall: {report['overall']}")
        if report.get("gmail", {}).get("smoke"):
            print(
                f"  Gmail smoke: {report['gmail']['smoke']['queries_executed']} queries, "
                f"{sum(r['threads_found'] for r in report['gmail']['smoke']['results'])} threads found"
            )
        if report.get("calendar", {}).get("smoke"):
            print(
                f"  Calendar smoke: {report['calendar']['smoke']['total_events_upcoming_14d']} events, "
                f"{report['calendar']['smoke']['interview_relevant']} interview-relevant"
            )
        if report.get("drive", {}).get("smoke"):
            print(
                f"  Drive smoke: {report['drive']['smoke']['total_files_listed']} files, "
                f"{report['drive']['smoke']['career_artifacts_found']} career artifacts"
            )

    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
