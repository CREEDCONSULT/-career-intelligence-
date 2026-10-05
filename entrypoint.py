#!/usr/bin/env python3
"""
Career Intelligence Dashboard - Python Entrypoint
Starts Streamlit immediately, runs pipeline in background thread.
"""
import subprocess
import time
import os
import sys
import threading
import requests

PORT = os.environ.get("PORT", "8501")
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "0")
DB_PATH = "/app/data/processed/career_intel.duckdb"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def run_streamlit():
    cmd = [
        "streamlit", "run", "streamlit_app/app.py",
        "--server.port", PORT,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        "--server.enableWebsocketCompression", "false",
    ]
    log(f"Starting Streamlit: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in proc.stdout:
        print(line.rstrip(), flush=True)
    proc.wait()

def wait_for_health(port, max_wait=120):
    url = f"http://localhost:{port}/_stcore/health"
    for i in range(max_wait):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                log(f"Streamlit healthy! (took {i+1}s)")
                return True
        except Exception:
            pass
        time.sleep(1)
    log(f"ERROR: Health check timeout after {max_wait}s")
    return False

def run_pipeline():
    log("Starting data pipeline in background...")
    
    if os.path.exists(DB_PATH) and FORCE_REFRESH != "1":
        log("Database exists, skipping pipeline (set FORCE_REFRESH=1 to re-run)")
        return
    
    log("Running data pipeline...")
    scripts = [
        ("download_job_bank_postings.py", "Job Bank postings"),
        ("download_job_bank_wages.py", "Job Bank wages"),
        ("download_statscan_jvws.py", "StatsCan JVWS"),
        ("download_indeed_trends.py", "Indeed trends"),
        ("transform.py", "Transform"),
    ]
    
    for script, name in scripts:
        log(f"Running {name}...")
        result = subprocess.run(
            [sys.executable, f"scripts/{script}"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            log(f"WARNING: {name} failed: {result.stderr[:500]}")
        else:
            log(f"Completed {name}")
    
    log("Pipeline complete")

def main():
    log("=== Career Intelligence Dashboard Starting ===")
    log(f"PORT: {PORT}, FORCE_REFRESH: {FORCE_REFRESH}")
    log(f"Python: {sys.version.split()[0]}")
    
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()
    
    log("Waiting for Streamlit health check...")
    if not wait_for_health(PORT, max_wait=120):
        log("ERROR: Streamlit failed to start")
        sys.exit(1)
    
    log("Streamlit is healthy! Starting pipeline in background...")
    
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    
    log("Dashboard ready. Streaming logs...")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log("Shutting down...")

if __name__ == "__main__":
    main()
