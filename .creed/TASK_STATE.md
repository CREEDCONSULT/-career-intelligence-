# TASK STATE - -career-intelligence--main

**Objective:** Recover the Career Intelligence codebase to a known-good, testable baseline after the previous session corrupted app.py and destroyed transform.py; then document current state, gaps, integration boundaries, and the next milestone plan
**Task:** task_ffc2eeecff | **Agent:** unknown | **Model:** ? (?)
**Updated:** 2026-10-05T18:47:55.508Z

## NEXT ACTION
> M2 accepted as COMPLETE WITH CONDITIONS. Founder actions to clear conditions: (1) set ANTHROPIC_API_KEY and run scripts/validate_live_model.py; (2) run scripts/extract_skills_llm.py without --fixture to populate production job_skills_llm; (3) authorize Gmail/Calendar/Drive via OAuth2 if live integrations wanted. M3 backlog ranked in CAREER_INTELLIGENCE_M2_REPORT.md section 14 (top: live-provider quality pass, Gmail thread import, Job Bank browse UI). Validation: use C:\Users\daunt\AppData\Local\Programs\Python\Python311\python.exe (bare python resolves to the Hermes venv); ruff check src scripts streamlit_app; pytest -q (expect 301 passed + 1 known data-gap failure + 3 live-skips); streamlit run streamlit_app/app.py (11 surfaces, unchanged from M1).


Last checkpoint: C:\Users\daunt\Downloads\-career-intelligence--main\-career-intelligence--main\.creed\checkpoints\2026-10-05T18-47-55-437Z-m2-complete-with-conditions-live-operati.json
