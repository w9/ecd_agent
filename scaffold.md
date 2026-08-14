# Scaffold Instructions for Clinical Site Feasibility AI Assistant Starter

You are an AI coding agent. Create a **local starter repository** that closely mirrors the private starter repository described in the Genentech/Roche SE7 Onsite Exercise Candidate Guide (Principal Software Engineer – Early Clinical Development).

The goal is a clean, runnable Python project that a candidate can immediately extend during a timed interview. **Do not implement the full solution** (no RAG indexing, no main query endpoint logic, no agent routing). Only provide the scaffolding that the guide says the starter supplies.

## Target Project Structure

```
clinical-site-feasibility/
├── README.md
├── pyproject.toml          # or requirements.txt + setup.cfg
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app with /health only
│   └── config.py           # simple settings
├── scripts/
│   ├── fetch_protocols.py  # downloads public ClinicalTrials.gov JSON
│   └── create_mock_site_data.py  # creates CSV + SQLite
├── data/                   # empty or with .gitkeep; will hold cached protocols + db
│   └── .gitkeep
├── tests/
│   └── test_health.py
└── examples/
    └── llm_smoke_test.py   # illustrative provider connection only
```

## Detailed Requirements

### 1. FastAPI Scaffold (highest priority)

- Create a minimal FastAPI application.
- Expose **only** a health endpoint: `GET /health` that returns `{"status": "ok"}`.
- Do **not** implement the main query endpoint, request/response schemas for the AI assistant, or any business logic.
- The application must start cleanly with `uvicorn app.main:app --reload`.
- Include a simple `app/config.py` that can later hold LLM API keys, data paths, etc. (use pydantic-settings or plain os.environ).

### 2. Protocol Fetcher Script

- `scripts/fetch_protocols.py`
- Must be able to download public study JSON from ClinicalTrials.gov (the classic API or the new v2 API).
- Accept one or more NCT IDs (or a small hardcoded list of public trials) as input.
- Save raw JSON files under `data/protocols/` (create the directory if needed).
- Print clear success/failure messages.
- Do **not** implement parsing, chunking, embedding, or retrieval. Those are left for the candidate.

Suggested public NCT IDs for testing (any recent, open trials are fine):
- NCT04516746
- NCT04368728
- NCT04470427

### 3. Mock Site Data Script

- `scripts/create_mock_site_data.py`
- Generate a realistic but **fake** CSV and an equivalent SQLite table containing site enrollment attributes.
- Suggested columns (adjust as needed for realism):
  - `site_id` (e.g. SITE-001, SITE-002, …)
  - `site_name`
  - `country` / `region`
  - `monthly_enrollment_rate` (float)
  - `active_trials` (int)
  - `capacity` or `remaining_slots`
  - `therapeutic_area` (optional)
- Create both:
  - `data/sites.csv`
  - `data/sites.db` (SQLite) with a table named `sites`
- Include 8–15 synthetic sites. Make a few sites have missing or zero values so the candidate can demonstrate “I don’t have information” behavior later.
- Print a short summary of what was created.

### 4. LLM Connectivity Example (smoke test only)

- `examples/llm_smoke_test.py`
- Provide a minimal, clearly labeled example of calling an LLM (OpenAI-compatible, Anthropic, or a local endpoint).
- It should be a pure smoke test: send a short prompt and print the response.
- Make it easy to swap providers via environment variables.
- Do **not** wire this into the FastAPI app. The guide states this is illustrative only.

### 5. Supporting Files

- **README.md**: Explain how to:
  - Create a virtualenv / install dependencies
  - Run the health endpoint
  - Execute the two scripts
  - Run the LLM smoke test
  - Note that the real interview uses a private GitHub repo and that candidates must not push solutions publicly.
- **.env.example**: Placeholder for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_BASE_URL`, etc.
- **.gitignore**: Standard Python + data/ (except .gitkeep), .env, __pycache__, etc.
- **tests/test_health.py**: Simple pytest that hits `/health`.
- Use Python 3.11+ style. Prefer `pyproject.toml` with modern tooling, but a plain `requirements.txt` is also acceptable.

## Constraints (mirror the official guide)

- No Roche/Genentech internal data, real patient data, or secrets.
- Keep the project self-contained and runnable offline after the protocols are cached and the mock DB is created.
- Do not implement RAG, tool-calling routers, Pydantic request models for the assistant, or any of the core interview deliverables.
- The resulting folder should feel like the official starter the candidate would clone on interview day.

## Acceptance Checklist for the Scaffold

- [ ] `uvicorn app.main:app` starts and `/health` returns 200
- [ ] `python scripts/fetch_protocols.py` downloads at least one public ClinicalTrials.gov JSON
- [ ] `python scripts/create_mock_site_data.py` produces both CSV and SQLite with realistic fake site rows
- [ ] `python examples/llm_smoke_test.py` can be pointed at a real or mock LLM endpoint
- [ ] README contains clear setup and run instructions
- [ ] No full solution code is present

After creating the files, print a short tree of the project and confirm the health endpoint works.
