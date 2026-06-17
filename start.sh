#!/bin/bash
set -euo pipefail

echo "=== Career Intelligence Dashboard Startup ==="
echo "PORT: 8501"
echo "FORCE_REFRESH: 0"
echo "Python: "

DB_PATH="/app/data/processed/career_intel.duckdb"

# Run pipeline if needed
if [ ! -f "" ] || [ "0" = "1" ]; then
    echo "Database not found or FORCE_REFRESH=1. Running data pipeline..."
    
    echo "[1/4] Downloading Job Bank postings..."
    python scripts/download_job_bank_postings.py 2>&1 | tee /tmp/jb_postings.log || echo "WARNING: Job Bank postings failed (see /tmp/jb_postings.log)"
    
    echo "[2/4] Downloading Job Bank wages..."
    python scripts/download_job_bank_wages.py 2>&1 | tee /tmp/jb_wages.log || echo "WARNING: Job Bank wages failed (see /tmp/jb_wages.log)"
    
    echo "[3/4] Downloading StatsCan JVWS..."
    python scripts/download_statscan_jvws.py 2>&1 | tee /tmp/statscan.log || echo "WARNING: StatsCan failed (see /tmp/statscan.log)"
    
    echo "[4/4] Downloading Indeed trends..."
    python scripts/download_indeed_trends.py 2>&1 | tee /tmp/indeed.log || echo "WARNING: Indeed trends failed (see /tmp/indeed.log)"
    
    echo "Transforming data..."
    python scripts/transform.py 2>&1 | tee /tmp/transform.log || { echo "ERROR: Transform failed (see /tmp/transform.log)"; exit 1; }
    
    echo "Pipeline complete."
else
    echo "Database found at . Skipping pipeline (set FORCE_REFRESH=1 to re-run)."
fi

# Verify database exists and has data
if [ -f "" ]; then
    echo "Database verified at "
    python -c "
import duckdb
c = duckdb.connect('', read_only=True)
for t in ['job_postings','job_skills','wages_job_bank','vacancies_statscan','indeed_trends']:
    try:
        cnt = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t}: {cnt:,} rows')
    except Exception as e:
        print(f'  {t}: ERROR - {e}')
"
else
    echo "WARNING: Database not found after pipeline!"
fi

# Start Streamlit with explicit port binding and verify it's up
PORT_NUM=8501
echo "Starting Streamlit on port ..."

# Start Streamlit in background so we can test it
streamlit run streamlit_app/app.py     --server.port=     --server.address=0.0.0.0     --server.headless=true     --server.enableCORS=false     --server.enableXsrfProtection=false     --server.enableWebsocketCompression=false     &

STREAMLIT_PID=
echo "Streamlit started with PID "

# Wait for Streamlit to be ready (max 60 seconds)
echo "Waiting for Streamlit to be ready on port ..."
for i in {1..60}; do
    if curl -sf "http://localhost:/_stcore/health" > /dev/null 2>&1; then
        echo "Streamlit is healthy!"
        break
    fi
    if ! kill -0  2>/dev/null; then
        echo "ERROR: Streamlit process died!"
        exit 1
    fi
    sleep 1
    if [  -eq 60 ]; then
        echo "ERROR: Streamlit health check timed out after 60 seconds"
        kill  2>/dev/null
        exit 1
    fi
done

echo "Streamlit is ready. Handing over to process manager..."
wait 
