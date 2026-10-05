
def init_user_tables(conn):
    """Create tables for user data if they don't exist."""
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

