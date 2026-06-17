# Railway deployment for Streamlit + Data Pipeline
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends     gcc     curl     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/data/raw/job_bank_postings /app/data/raw/job_bank_wages /app/data/raw/statscan /app/data/raw/indeed /app/data/processed /app/logs

RUN python -m spacy download en_core_web_sm

EXPOSE 8501

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
