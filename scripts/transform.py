#!/usr/bin/env python3
"""
Transform raw data -> processed DuckDB.
Run after downloaders.
"""
import duckdb
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import json

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "career_intel.duckdb"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    
    # Create tables
    conn.execute("""
    CREATE TABLE IF NOT EXISTS job_postings (
        id INTEGER PRIMARY KEY,
        source VARCHAR,
        source_id VARCHAR,
        title VARCHAR,
        noc_code VARCHAR,
        naics_code VARCHAR,
        location VARCHAR,
        location_normalized VARCHAR,
        vacancies INTEGER,
        salary_min DOUBLE,
        salary_max DOUBLE,
        salary_median DOUBLE,
        hours VARCHAR,
        employment_terms VARCHAR,
        requirements_text TEXT,
        posted_date DATE,
        scraped_date DATE
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS job_skills (
        job_id INTEGER REFERENCES job_postings(id),
        skill_id VARCHAR,
        skill_name VARCHAR,
        category VARCHAR,
        subcategory VARCHAR,
        confidence DOUBLE
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS wages_job_bank (
        noc_code VARCHAR,
        year INTEGER,
        region VARCHAR,
        min_wage DOUBLE,
        median_wage DOUBLE,
        max_wage DOUBLE,
        PRIMARY KEY (noc_code, year, region)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS vacancies_statscan (
        noc_code VARCHAR,
        year INTEGER,
        quarter INTEGER,
        region VARCHAR,
        vacancy_count INTEGER,
        avg_offered_wage DOUBLE,
        PRIMARY KEY (noc_code, year, quarter, region)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS indeed_trends (
        date DATE,
        geography VARCHAR,
        sector VARCHAR,
        postings_index DOUBLE,
        wage_growth_yoy DOUBLE,
        ai_share DOUBLE,
        PRIMARY KEY (date, geography, sector)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS noc_mapping (
        noc_code VARCHAR PRIMARY KEY,
        title VARCHAR,
        category VARCHAR
    )
    """)
    
    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_postings_date ON job_postings(posted_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_postings_noc ON job_postings(noc_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills(job_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill_id)")
    
    return conn

def load_job_bank_postings(conn):
    """Load filtered Toronto postings."""
    postings_dir = RAW_DIR / "job_bank_postings"
    files = list(postings_dir.glob("toronto_*.csv"))
    
    if not files:
        print("No filtered Toronto posting files found")
        return 0
    
    total = 0
    for f in tqdm(files, desc="Loading postings"):
        try:
            df = pd.read_csv(f, low_memory=False)
            
            # Normalize columns
            cols = df.columns.str.lower().str.strip()
            df.columns = cols
            
            # Map to schema
            mapping = {
                'job title': 'title',
                'noc code': 'noc_code',
                'naics code': 'naics_code',
                'work location': 'location',
                'number of vacancies': 'vacancies',
                'salary': 'salary_median',
                'hours of work': 'hours',
                'employment terms': 'employment_terms',
                'job requirements': 'requirements_text',
                'posting date': 'posted_date',
            }
            
            df = df.rename(columns=mapping)
            
            # Parse salary range if present
            if 'salary' in df.columns:
                # Try to extract min/max from salary text
                pass
            
            # Add metadata
            df['source'] = 'job_bank'
            df['source_id'] = range(1, len(df) + 1)
            df['location_normalized'] = df['location'].str.lower().str.strip()
            df['scraped_date'] = pd.Timestamp.now().date()
            
            # Parse dates
            if 'posted_date' in df.columns:
                df['posted_date'] = pd.to_datetime(df['posted_date'], errors='coerce').dt.date
            
            # Insert in chunks
            for chunk in [df[i:i+1000] for i in range(0, len(df), 1000)]:
                conn.execute("INSERT INTO job_postings SELECT * FROM chunk", {"chunk": chunk})
                total += len(chunk)
        except Exception as e:
            print(f"Error loading {f}: {e}")
    
    return total

def load_job_bank_wages(conn):
    """Load Toronto wage data."""
    wages_dir = RAW_DIR / "job_bank_wages"
    files = list(wages_dir.glob("toronto_*.csv"))
    
    if not files:
        return 0
    
    total = 0
    for f in tqdm(files, desc="Loading wages"):
        try:
            df = pd.read_csv(f)
            # Filter Toronto already done in downloader
            for chunk in [df[i:i+1000] for i in range(0, len(df), 1000)]:
                conn.execute("INSERT INTO wages_job_bank SELECT * FROM chunk", {"chunk": chunk})
                total += len(chunk)
        except Exception as e:
            print(f"Error loading wages {f}: {e}")
    
    return total

def load_statscan_jvws(conn):
    """Load StatsCan JVWS Toronto data."""
    jvws_dir = RAW_DIR / "statscan"
    files = list(jvws_dir.glob("jvws_toronto.csv"))
    
    if not files:
        return 0
    
    total = 0
    for f in tqdm(files, desc="Loading StatsCan JVWS"):
        try:
            df = pd.read_csv(f)
            for chunk in [df[i:i+1000] for i in range(0, len(df), 1000)]:
                conn.execute("INSERT INTO vacancies_statscan SELECT * FROM chunk", {"chunk": chunk})
                total += len(chunk)
        except Exception as e:
            print(f"Error loading StatsCan {f}: {e}")
    
    return total

def load_indeed_trends(conn):
    """Load Indeed Hiring Lab trends."""
    indeed_dir = RAW_DIR / "indeed"
    files = list(indeed_dir.glob("indeed_*.csv"))
    
    if not files:
        return 0
    
    total = 0
    for f in tqdm(files, desc="Loading Indeed trends"):
        try:
            df = pd.read_csv(f)
            # Normalize date column
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'ref_date' in c.lower()]
            if date_cols:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors='coerce').dt.date
            
            for chunk in [df[i:i+1000] for i in range(0, len(df), 1000)]:
                conn.execute("INSERT INTO indeed_trends SELECT * FROM chunk", {"chunk": chunk})
                total += len(chunk)
        except Exception as e:
            print(f"Error loading Indeed {f}: {e}")
    
    return total

def load_noc_mapping(conn):
    """Load NOC code to title mapping."""
    from pipeline.noc_mapper import NOCMapper
    mapper = NOCMapper()
    
    records = []
    for code, title in mapper.noc_to_title.items():
        cat = mapper.noc_to_category.get(code, "Unknown")
        records.append({"noc_code": code, "title": title, "category": cat})
    
    df = pd.DataFrame(records)
    conn.execute("INSERT INTO noc_mapping SELECT * FROM df", {"df": df})
    print(f"Loaded {len(records)} NOC mappings")

def extract_skills_for_postings(conn):
    """Run skill extraction on loaded postings."""
    from pipeline.skill_taxonomy import get_taxonomy

    taxonomy = get_taxonomy()
    
    # Get postings without skills yet
    df = conn.execute("""
        SELECT id, requirements_text FROM job_postings
        WHERE id NOT IN (SELECT DISTINCT job_id FROM job_skills)
        AND requirements_text IS NOT NULL
        AND requirements_text != ''
    """).df()
    
    print(f"Extracting skills for {len(df)} postings...")
    
    skills_records = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Extracting skills"):
        skills = taxonomy.extract_skills_from_text(row['requirements_text'])
        for skill in skills:
            skills_records.append({
                "job_id": row['id'],
                "skill_id": skill['skill_id'],
                "skill_name": skill['skill_name'],
                "category": skill['category'],
                "subcategory": skill['subcategory'],
                "confidence": skill['confidence']
            })
    
    if skills_records:
        skills_df = pd.DataFrame(skills_records)
        conn.execute("INSERT INTO job_skills SELECT * FROM skills_df", {"skills_df": skills_df})
        print(f"Extracted {len(skills_records)} skill mentions")

def main():
    print("Initializing DuckDB...")
    conn = init_db()
    
    print("\n=== Loading Data ===")
    load_noc_mapping(conn)
    load_job_bank_postings(conn)
    load_job_bank_wages(conn)
    load_statscan_jvws(conn)
    load_indeed_trends(conn)
    
    print("\n=== Extracting Skills ===")
    extract_skills_for_postings(conn)
    
    print("\n=== Verification ===")
    tables = [
        "job_postings", "job_skills", "wages_job_bank",
        "vacancies_statscan", "indeed_trends", "noc_mapping"
    ]
    for t in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {count:,} rows")
        except:
            print(f"  {t}: ERROR")
    
    conn.close()
    print("\nTransform complete!")

if __name__ == "__main__":
    main()
