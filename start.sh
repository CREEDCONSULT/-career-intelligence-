#!/bin/bash
set -euo pipefail

echo "=== Career Intelligence Dashboard Startup ==="
echo "PORT: 8501"
echo "FORCE_REFRESH: 0"
echo "Python: "
echo "PWD: /mnt/c/Users/daunt"
echo "PORT env: "
echo "Railway PORT env check: NOT_SET"

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

PORT_NUM=8501
echo "Starting Streamlit on port ..."

# Debug: show what's listening
echo "Pre-start netstat:"
netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null || echo "netstat/ss not available"

# Start Streamlit in background with more verbose output
streamlit run streamlit_app/app.py     --server.port=     --server.address=0.0.0.0     --server.headless=true     --server.enableCORS=false     --server.enableXsrfProtection=false     --server.enableWebsocketCompression=false     --logger.level=debug     2>&1 | tee /tmp/streamlit.log &

STREAMLIT_PID=
echo "Streamlit started with PID "

# Give Streamlit a moment to start
sleep 3

# Debug: check if process is alive
if ! kill -0  2>/dev/null; then
    echo "ERROR: Streamlit process died immediately!"
    echo "Streamlit log:"
    cat /tmp/streamlit.log
    exit 1
fi

# Debug: check what's listening
echo "Post-start netstat:"
netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null || echo "netstat/ss not available"

# Wait for Streamlit to be ready (max 90 seconds)
echo "Waiting for Streamlit to be ready on port ..."
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
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90; do
    if curl -sf "http://localhost:/_stcore/health" > /dev/null 2>&1; then
        echo "Streamlit is healthy! (took  seconds)"
        break
    fi
    if ! kill -0  2>/dev/null; then
        echo "ERROR: Streamlit process died!"
        echo "Streamlit log:"
        cat /tmp/streamlit.log
        exit 1
    fi
    if [  -eq 90 ]; then
        echo "ERROR: Streamlit health check timed out after 90 seconds"
        echo "Streamlit log:"
        cat /tmp/streamlit.log
        exit 1
    fi
    sleep 1
done

echo "Streamlit is ready. Handing over to process manager..."
wait 
