# Railway deployment for Streamlit + Data Pipeline
FROM python:3.11-slim

# Install system dependencies needed for Playwright, DuckDB, pandas, curl
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     g++     curl     libsqlite3-dev     libpq-dev     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright with only chromium (no system deps - already installed above)
RUN playwright install chromium

COPY . .

RUN mkdir -p /app/data/raw/job_bank_postings /app/data/raw/job_bank_wages /app/data/raw/statscan /app/data/raw/indeed /app/data/processed /app/logs

# spaCy model already downloaded in base image build, but ensure it exists
RUN python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || python -m spacy download en_core_web_sm

EXPOSE 8501

COPY entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py

CMD ["python", "/entrypoint.py"]
