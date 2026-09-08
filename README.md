# Clinical Site Feasibility AI Assistant

Local service that answers free-text questions about public clinical trial protocols and mock site enrollment data.

It combines:

- A FastAPI backend with `GET /health` and `POST /query`
- Retrieval over cached ClinicalTrials.gov study text
- Tool calls into a SQLite site table for enrollment metrics
- An optional Vite + React chat UI

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python + dependencies)
- Python **3.11+** (uv can install a matching interpreter if needed)
- Network access to ClinicalTrials.gov (for protocol fetch) and an LLM endpoint (for query answers and the smoke test)
- Node.js (only if you run the chat UI)

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env with any LLM credentials you plan to use
```

This creates `.venv`, installs runtime + dev dependencies, and uses the locked versions in `uv.lock`.

`just setup` also installs the chat UI dependencies.

## Run the API

```bash
uv run uvicorn app.main:app --reload
# or: just dev
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}

just query "What is the enrollment rate for SITE-001?"
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

## Fetch and ingest public protocol data

Downloads ClinicalTrials.gov API v2 JSON into `data/protocols/`, then indexes chunks:

```bash
uv run python scripts/fetch_protocols.py
# or specific studies:
uv run python scripts/fetch_protocols.py NCT04516746 NCT04368728 NCT04470427

uv run python scripts/ingest_protocols.py
```

`just data` runs fetch, ingest, and mock site creation together.

## Create mock site data

Creates synthetic site enrollment attributes:

```bash
uv run python scripts/create_mock_site_data.py
```

Outputs:

- `data/sites.csv`
- `data/sites.db` (SQLite table `sites`)

A few sites have zero or missing values so “no information” answers can be demonstrated.

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
├── TASK.md
├── SPECS.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── app/
│   ├── main.py             # FastAPI: /health, /query, /protocols
│   ├── query.py
│   ├── config.py
│   ├── agent/              # tool-using loop
│   ├── rag/                # parse, chunk, SQLite FTS
│   └── tools/              # site + protocol tools
├── scripts/
│   ├── fetch_protocols.py
│   ├── ingest_protocols.py
│   └── create_mock_site_data.py
├── data/                   # cached protocols + site db (gitignored contents)
├── tests/
├── web/                    # Vite + React chat UI
└── examples/
    └── llm_smoke_test.py
```

## Constraints

- Use only public trial information and the supplied mock site data.
- Do not commit secrets, credentials, or real patient data.
