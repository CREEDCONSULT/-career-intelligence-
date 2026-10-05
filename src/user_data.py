import duckdb
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import os

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "career_intel.duckdb"

def get_conn():
    return duckdb.connect(str(DB_PATH))

def init_user_tables():
    """Initialize user data tables if they don't exist."""
    conn = get_conn()
    try:
        # career_profile table
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
        # user_skills table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_skills (
                id INTEGER PRIMARY KEY,
                skill_name VARCHAR,
                proficiency_level VARCHAR,
                credibility_level VARCHAR,
                years_experience DOUBLE,
                last_used_date DATE
            )
        """)
        # user_evidence table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_evidence (
                id INTEGER PRIMARY KEY,
                skill_id INTEGER,
                title VARCHAR,
                description VARCHAR,
                date_achieved DATE,
                context VARCHAR,
                impact_metrics VARCHAR,
                verification_status VARCHAR,
                verification_documents VARCHAR,
                external_links VARCHAR,
                file_attachments VARCHAR,
                FOREIGN KEY (skill_id) REFERENCES user_skills (id)
            )
        """)
        # user_applications table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_applications (
                id INTEGER PRIMARY KEY,
                opportunity_id INTEGER,
                application_date DATE,
                status VARCHAR,
                application_materials VARCHAR,
                next_best_action VARCHAR,
                FOREIGN KEY (opportunity_id) REFERENCES job_postings (id)
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
        # Get column names
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
            # Insert new profile
            columns = ", ".join(profile.keys())
            placeholders = ", ".join(["?" for _ in profile])
            values = tuple(profile.values())
            conn.execute(f"INSERT INTO career_profile ({columns}) VALUES ({placeholders})", values)
        else:
            # Update existing profile
            set_clause = ", ".join([f"{k} = ?" for k in profile.keys()])
            values = tuple(profile.values())
            conn.execute(f"UPDATE career_profile SET {set_clause} WHERE id = ?", values + (existing["id"],))
    finally:
        conn.close()

def get_user_skills() -> List[Dict[str, Any]]:
    """Get all user skills."""
    conn = get_conn()
    try:
        result = conn.execute("SELECT * FROM user_skills").fetchdf()
        return result.to_dict('records')
    finally:
        conn.close()

def add_user_skill(skill: Dict[str, Any]):
    """Add a new user skill."""
    conn = get_conn()
    try:
        columns = ", ".join(skill.keys())
        placeholders = ", ".join(["?" for _ in skill])
        values = tuple(skill.values())
        conn.execute(f"INSERT INTO user_skills ({columns}) VALUES ({placeholders})", values)
    finally:
        conn.close()

def update_user_skill(skill_id: int, skill: Dict[str, Any]):
    """Update an existing user skill."""
    conn = get_conn()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in skill.keys()])
        values = tuple(skill.values())
        conn.execute(f"UPDATE user_skills SET {set_clause} WHERE id = ?", values + (skill_id,))
    finally:
        conn.close()

def get_user_evidence() -> List[Dict[str, Any]]:
    """Get all user evidence."""
    conn = get_conn()
    try:
        result = conn.execute("SELECT * FROM user_evidence").fetchdf()
        return result.to_dict('records')
    finally:
        conn.close()

def add_user_evidence(evidence: Dict[str, Any]):
    """Add a new user evidence."""
    conn = get_conn()
    try:
        columns = ", ".join(evidence.keys())
        placeholders = ", ".join(["?" for _ in evidence])
        values = tuple(evidence.values())
        conn.execute(f"INSERT INTO user_evidence ({columns}) VALUES ({placeholders})", values)
    finally:
        conn.close()

def update_user_evidence(evidence_id: int, evidence: Dict[str, Any]):
    """Update an existing user evidence."""
    conn = get_conn()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in evidence.keys()])
        values = tuple(evidence.values())
        conn.execute(f"UPDATE user_evidence SET {set_clause} WHERE id = ?", values + (evidence_id,))
    finally:
        conn.close()

def get_user_applications() -> List[Dict[str, Any]]:
    """Get all user applications."""
    conn = get_conn()
    try:
        result = conn.execute("SELECT * FROM user_applications").fetchdf()
        return result.to_dict('records')
    finally:
        conn.close()

def add_user_application(application: Dict[str, Any]):
    """Add a new user application."""
    conn = get_conn()
    try:
        columns = ", ".join(application.keys())
        placeholders = ", ".join(["?" for _ in application])
        values = tuple(application.values())
        conn.execute(f"INSERT INTO user_applications ({columns}) VALUES ({placeholders})", values)
    finally:
        conn.close()

def update_user_application(application_id: int, application: Dict[str, Any]):
    """Update an existing user application."""
    conn = get_conn()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in application.keys()])
        values = tuple(application.values())
        conn.execute(f"UPDATE user_applications SET {set_clause} WHERE id = ?", values + (application_id,))
    finally:
        conn.close()
