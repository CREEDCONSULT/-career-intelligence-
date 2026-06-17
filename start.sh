#!/bin/bash
set -euo pipefail

echo "=== Career Intelligence Dashboard Startup ==="
echo "PORT: 8501"
echo "FORCE_REFRESH: 0"
echo "Python: "

DB_PATH="/app/data/processed/career_intel.duckdb"

PORT_NUM=8501

# START STREAMLIT IMMEDIATELY IN BACKGROUND
echo "Starting Streamlit on port  immediately..."
streamlit run streamlit_app/app.py     --server.port=     --server.address=0.0.0.0     --server.headless=true     --server.enableCORS=false     --server.enableXsrfProtection=false     --server.enableWebsocketCompression=false     2>&1 | tee /tmp/streamlit.log &

STREAMLIT_PID=
echo "Streamlit started with PID "

# Wait for Streamlit to be ready (healthcheck will pass)
echo "Waiting for Streamlit to be ready..."
for i in 1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60; do
    if curl -sf "http://localhost:/_stcore/health" > /dev/null 2>&1; then
        echo "Streamlit is healthy! (took  seconds)"
        break
    fi
    if ! kill -0  2>/dev/null; then
        echo "ERROR: Streamlit process died!"
        cat /tmp/streamlit.log
        exit 1
    fi
    sleep 1
done

# NOW RUN PIPELINE IN BACKGROUND WHILE STREAMLIT SERVES
echo "Streamlit is ready. Starting data pipeline in background..."

DB_PATH="/app/data/processed/career_intel.duckdb"

if [ ! -f "" ] || [ "0" = "1" ]; then
    echo "Database not found or FORCE_REFRESH=1. Running data pipeline in background..."
    
    (
        echo "[1/4] Downloading Job Bank postings..."
        python scripts/download_job_bank_postings.py 2>&1 | tee /tmp/jb_postings.log || echo "WARNING: Job Bank postings failed"
        
        echo "[2/4] Downloading Job Bank wages..."
        python scripts/download_job_bank_wages.py 2>&1 | tee /tmp/jb_wages.log || echo "WARNING: Job Bank wages failed"
        
        echo "[3/4] Downloading StatsCan JVWS..."
        python scripts/download_statscan_jvws.py 2>&1 | tee /tmp/statscan.log || echo "WARNING: StatsCan failed"
        
        echo "[4/4] Downloading Indeed trends..."
        python scripts/download_indeed_trends.py 2>&1 | tee /tmp/indeed.log || echo "WARNING: Indeed trends failed"
        
        echo "Transforming data..."
        python scripts/transform.py 2>&1 | tee /tmp/transform.log || echo "ERROR: Transform failed"
        
        echo "Pipeline complete."
    ) &
    
    PIPELINE_PID=
    echo "Pipeline started with PID  (running in background)"
else
    echo "Database found at . Skipping pipeline."
fi

# Keep Streamlit running in foreground
echo "Streamlit is running. Dashboard available at http://localhost:"
wait 
