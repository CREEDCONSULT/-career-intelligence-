# Railway deployment for Streamlit + Data Pipeline
FROM python:3.11-slim

# Install system dependencies needed for Playwright, DuckDB, pandas, curl
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     g++     curl     libsqlite3-dev     libpq-dev     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install the local `pipeline` package so `from pipeline.X import ...` resolves at runtime
RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data/raw/job_bank_postings /app/data/raw/job_bank_wages /app/data/raw/statscan /app/data/raw/indeed /app/data/processed /app/logs

EXPOSE 8501

COPY entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py

CMD ["python", "/entrypoint.py"]
