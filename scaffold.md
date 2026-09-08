# Project bootstrap

Notes for the initial layout of this repository: a runnable Python service with a health check, protocol download, mock site data, and an LLM smoke test. Query routing, RAG, and the chat UI were added on top of that base.

## Target layout

```
clinical-site-feasibility/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   └── config.py           # settings from the environment
├── scripts/
│   ├── fetch_protocols.py  # downloads public ClinicalTrials.gov JSON
│   └── create_mock_site_data.py  # creates CSV + SQLite
├── data/                   # cached protocols + db
│   └── .gitkeep
├── tests/
│   └── test_health.py
└── examples/
    └── llm_smoke_test.py
```

## Bootstrap pieces

### 1. FastAPI app

- Minimal FastAPI application.
- `GET /health` returns `{"status": "ok"}`.
- Starts with `uvicorn app.main:app --reload`.
- `app/config.py` holds LLM keys, data paths, and related settings (pydantic-settings or `os.environ`).

### 2. Protocol fetcher

- `scripts/fetch_protocols.py`
- Download public study JSON from ClinicalTrials.gov (classic API or v2).
- Accept one or more NCT IDs, or a small hardcoded list of public trials.
- Save raw JSON under `data/protocols/` (create the directory if needed).
- Print clear success/failure messages.

Suggested public NCT IDs:

- NCT04516746
- NCT04368728
- NCT04470427

### 3. Mock site data

- `scripts/create_mock_site_data.py`
- Generate a realistic but fake CSV and matching SQLite table of site enrollment attributes.
- Suggested columns:
  - `site_id` (e.g. SITE-001, SITE-002, …)
  - `site_name`
  - `country` / `region`
  - `monthly_enrollment_rate` (float)
  - `active_trials` (int)
  - `capacity` or `remaining_slots`
  - `therapeutic_area` (optional)
- Write both:
  - `data/sites.csv`
  - `data/sites.db` (SQLite) with a table named `sites`
- Include 8–15 synthetic sites. A few rows should have missing or zero values so “I don’t have information” answers are testable.

### 4. LLM connectivity example

- `examples/llm_smoke_test.py`
- Minimal example of calling an LLM (OpenAI-compatible, Anthropic, or a local endpoint).
- Smoke test only: send a short prompt and print the response.
- Swap providers via environment variables.
- Not wired into the FastAPI app.

### 5. Supporting files

- **README.md**: virtualenv / install, health endpoint, scripts, LLM smoke test.
- **.env.example**: placeholders for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_BASE_URL`, etc.
- **.gitignore**: standard Python + `data/` (except `.gitkeep`), `.env`, `__pycache__`.
- **tests/test_health.py**: pytest against `/health`.
- Python 3.11+ with `pyproject.toml` (or a plain `requirements.txt`).

## Constraints

- No real patient data or secrets.
- Keep the project self-contained and runnable offline after protocols are cached and the mock DB is created.

## Bootstrap checklist

- [ ] `uvicorn app.main:app` starts and `/health` returns 200
- [ ] `python scripts/fetch_protocols.py` downloads at least one public ClinicalTrials.gov JSON
- [ ] `python scripts/create_mock_site_data.py` produces both CSV and SQLite with realistic fake site rows
- [ ] `python examples/llm_smoke_test.py` can be pointed at a real or mock LLM endpoint
- [ ] README contains clear setup and run instructions
