"""Career-profile persistence (user's target/identity fields).

M1 note: the previous sketchy skills/evidence/applications DAOs and tables
(``user_skills``, ``user_evidence``, ``user_applications``) have been
superseded by the canonical ``careeros`` stores:

- evidence      -> ``careeros.evidence.EvidenceStore``      (evidence_items)
- applications  -> ``careeros.application.ApplicationStore`` (applications +
                   application_events, application_documents)
- skills        -> derived from evidence (evidence-backed by design)

This module intentionally keeps only the single-row career profile. The
superseded empty tables are dropped once by ``migrate_superseded_tables``.
"""

import duckdb
from pathlib import Path
from typing import Optional, Dict, Any

ROOT = Path(__file__).resolve().parents[1]  # repo root (src/user_data.py -> repo)
DB_PATH = ROOT / "data" / "processed" / "career_intel.duckdb"

_SUPERSEDED = ("user_skills", "user_evidence", "user_applications")


def get_conn():
    return duckdb.connect(str(DB_PATH))


def _table_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [name]
        ).fetchone()[0]
        > 0
    )


def migrate_superseded_tables() -> list[str]:
    """One-time cleanup: drop the pre-M1 empty sketch tables if present.

    Only drops a table when it holds ZERO rows - any real data is preserved
    (and reported) rather than destroyed. Returns the dropped table names.
    """
    dropped = []
    conn = get_conn()
    try:
        for t in _SUPERSEDED:
            if _table_exists(conn, t):
                n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                if n == 0:
                    conn.execute(f"DROP TABLE {t}")
                    dropped.append(t)
    finally:
        conn.close()
    return dropped


def init_user_tables():
    """Initialize the career profile table if it doesn't exist."""
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS career_profile (
                id INTEGER PRIMARY KEY,
                name VARCHAR,
                location VARCHAR,
                target_role VARCHAR,
                target_location VARCHAR,
                target_salary_min DOUBLE,
                target_salary_max DOUBLE
            )
        """)
    finally:
        conn.close()


def get_career_profile() -> Optional[Dict[str, Any]]:
    """Get the career profile. Returns None if not exists."""
    conn = get_conn()
    try:
        result = conn.execute("SELECT * FROM career_profile LIMIT 1").fetchone()
        if result is None:
            return None
        column_names = [desc[0] for desc in conn.description]
        return dict(zip(column_names, result))
    finally:
        conn.close()


def set_career_profile(profile: Dict[str, Any]):
    """Set the career profile. If a profile exists, update it; otherwise, insert a new one."""
    conn = get_conn()
    try:
        existing = get_career_profile()
        if existing is None:
            columns = ", ".join(profile.keys())
            placeholders = ", ".join(["?" for _ in profile])
            values = tuple(profile.values())
            conn.execute(f"INSERT INTO career_profile ({columns}) VALUES ({placeholders})", values)
        else:
            set_clause = ", ".join([f"{k} = ?" for k in profile.keys()])
            values = tuple(profile.values())
            conn.execute(
                f"UPDATE career_profile SET {set_clause} WHERE id = ?", values + (existing["id"],)
            )
    finally:
        conn.close()
