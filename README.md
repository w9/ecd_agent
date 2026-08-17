# Clinical Site Feasibility AI Assistant — Starter

Local starter scaffold that mirrors the Genentech/Roche SE7 onsite exercise starter repository for Early Clinical Development.

This repository provides **scaffolding only**:

- FastAPI app with a `/health` endpoint
- Script to download public ClinicalTrials.gov study JSON
- Script to create fake site enrollment CSV + SQLite data
- Illustrative LLM connectivity smoke test

It does **not** include the interview solution (no RAG indexing, no main query endpoint, no agent routing).

> **Interview note:** The real exercise uses a private GitHub repository. Do **not** publish interview solutions to a public repository.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python + dependencies)
- Python **3.11+** (uv can install a matching interpreter if needed)
- Network access to ClinicalTrials.gov (for protocol fetch) and an LLM endpoint (for the smoke test)

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env with any LLM credentials you plan to use
```

This creates `.venv`, installs runtime + dev dependencies, and uses the locked versions in `uv.lock`.

## Run the health endpoint

```bash
uv run uvicorn app.main:app --reload
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Interactive docs (optional): http://127.0.0.1:8000/docs

## Local chat UI

The chat front end is a separate Vite + React + shadcn/ui app in `web/`. It talks to `POST /query` and `GET /protocols` through a Vite proxy.

```bash
# terminal 1 — API
just dev

# terminal 2 — chat UI (first time: cd web && npm install)
just chat
# http://127.0.0.1:5173
```

## Fetch public protocol data

Downloads ClinicalTrials.gov API v2 JSON into `data/protocols/`:

```bash
uv run python scripts/fetch_protocols.py
# or specific studies:
uv run python scripts/fetch_protocols.py NCT04516746 NCT04368728 NCT04470427
```

Parsing, chunking, indexing, and retrieval are left for the exercise.

## Create mock site data

Creates synthetic site enrollment attributes:

```bash
uv run python scripts/create_mock_site_data.py
```

Outputs:

- `data/sites.csv`
- `data/sites.db` (SQLite table `sites`)

Includes a few sites with zero/missing values so later “no information” behavior can be demonstrated.

## LLM smoke test (illustrative only)

Not wired into the FastAPI app. Verifies you can reach an LLM from this environment.

```bash
# OpenAI-compatible (default)
export LLM_PROVIDER=openai
export OPENAI_API_KEY=...
export LLM_BASE_URL=https://api.openai.com/v1   # or a local/proxy base URL
export LLM_MODEL=gpt-4o-mini
uv run python examples/llm_smoke_test.py

# Anthropic alternative
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...
uv run python examples/llm_smoke_test.py
```

## Tests

```bash
uv run pytest
```

## Project layout

```
.
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app with /health only
│   └── config.py
├── scripts/
│   ├── fetch_protocols.py
│   └── create_mock_site_data.py
├── data/                   # cached protocols + site db (gitignored contents)
├── tests/
│   └── test_health.py
└── examples/
    └── llm_smoke_test.py
```

## Constraints

- Use only public trial information and the supplied mock site data.
- Do not commit secrets, credentials, real patient data, or confidential company information.
