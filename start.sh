#!/bin/bash
set -e

echo "=== Career Intelligence Dashboard Startup ==="

DB_PATH="/app/data/processed/career_intel.duckdb"
if [ ! -f "" ] || [ "" = "1" ]; then
    echo "Database not found or FORCE_REFRESH=1. Running data pipeline..."
    
    echo "Downloading Job Bank postings..."
    python scripts/download_job_bank_postings.py || echo "WARNING: Job Bank postings download failed"
    
    echo "Downloading Job Bank wages..."
    python scripts/download_job_bank_wages.py || echo "WARNING: Job Bank wages download failed"
    
    echo "Downloading StatsCan JVWS..."
    python scripts/download_statscan_jvws.py || echo "WARNING: StatsCan download failed"
    
    echo "Downloading Indeed trends..."
    python scripts/download_indeed_trends.py || echo "WARNING: Indeed trends download failed"
    
    echo "Transforming data..."
    python scripts/transform.py || echo "WARNING: Transform failed"
    
    echo "Pipeline complete."
else
    echo "Database found at . Skipping pipeline (set FORCE_REFRESH=1 to re-run)."
fi

echo "Starting Streamlit on port ..."
exec streamlit run streamlit_app/app.py --server.port= --server.address=0.0.0.0 --server.headless=true
