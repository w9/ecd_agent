# Common commands for the clinical site feasibility assistant.
# `just` lists recipes. Extra args pass through: `just test -k health`.

set dotenv-load

host := "127.0.0.1"
port := "8000"
base_url := "http://" + host + ":" + port

# List available recipes
default:
    @just --list

# Install locked runtime + dev dependencies
sync:
    uv sync

# Create .env from the example if it is missing
env:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -f .env ]]; then
        echo ".env already exists"
    else
        cp .env.example .env
        echo "Created .env from .env.example — add LLM credentials if needed"
    fi

# Install Python deps, ensure .env exists, and install the chat UI
setup: sync env
    npm --prefix web install

# Run the FastAPI app with reload + LLM debug
# Chat UI is a separate Vite app: `just chat` → http://127.0.0.1:5173
dev:
    LLM_DEBUG=true uv run uvicorn app.main:app --reload --host {{ host }} --port {{ port }}

# Run the Vite + React chat UI (proxies /query and /protocols to the API)
chat:
    npm --prefix web run dev

# Run the FastAPI app without reload (production-like)
prod:
    uv run uvicorn app.main:app --host {{ host }} --port {{ port }}

# GET /health
health:
    curl -sS {{ base_url }}/health
    @echo

# POST /query  (just query "What is the enrollment rate for SITE-001?" [NCT04516746])
query q nct="":
    #!/usr/bin/env bash
    set -euo pipefail
    payload="$(uv run python -c 'import json,sys; body={"query":sys.argv[1]}; nct=sys.argv[2]; body.update({"nct_id":nct} if nct else {}); print(json.dumps(body))' {{ quote(q) }} {{ quote(nct) }})"
    curl -sS {{ base_url }}/query -H 'Content-Type: application/json' -d "$payload"
    echo

# Download ClinicalTrials.gov study JSON into data/protocols/
fetch *nct_ids:
    uv run python scripts/fetch_protocols.py {{ nct_ids }}

# Parse cached protocol JSON and write SQLite chunks
ingest:
    uv run python scripts/ingest_protocols.py

# Create synthetic site CSV + SQLite table
sites:
    uv run python scripts/create_mock_site_data.py

# Fetch protocols, ingest them, and create mock site data
data: fetch ingest sites

# Run the full pytest suite
test *args:
    uv run pytest {{ args }}

# Unit tests only (skip SPECS e2e)
test-unit:
    uv run pytest -m "not e2e"

# SPECS.md HTTP contract tests
test-e2e:
    uv run pytest -m e2e

# LLM connectivity smoke test (needs credentials in .env)
smoke:
    uv run python examples/llm_smoke_test.py
