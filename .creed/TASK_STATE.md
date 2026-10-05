# TASK STATE - -career-intelligence--main

**Objective:** Recover the Career Intelligence codebase to a known-good, testable baseline after the previous session corrupted app.py and destroyed transform.py; then document current state, gaps, integration boundaries, and the next milestone plan
**Task:** task_ffc2eeecff | **Agent:** unknown | **Model:** ? (?)
**Updated:** 2026-10-05T11:12:42.926Z

## NEXT ACTION
> Start M1 vertical slice: add opportunities table + DAO with backfill from job_postings, then posting-detail/shortlist UI (CAREER_INTELLIGENCE_RECOVERY_REPORT.md section 12, task 1). Run scripts/extract_skills_llm.py once with an API key to populate job_skills_llm (fixes the 1 red test). Validation: pip install -e ., ruff check src scripts streamlit_app, pytest -q (expect 100 pass + 1 known data-gap failure), streamlit run streamlit_app/app.py. Use system python C:\Users\daunt\AppData\Local\Programs\Python\Python311\python.exe - bare 'python' resolves to the Hermes venv without deps.


Last checkpoint: C:\Users\daunt\Downloads\-career-intelligence--main\-career-intelligence--main\.creed\checkpoints\2026-10-05T11-12-42-875Z-career-intelligence-recovered-to-known-g.json
