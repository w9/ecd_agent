#!/usr/bin/env python3
"""Illustrative LLM connectivity smoke test.

This script is NOT wired into the FastAPI app. It only verifies that you can
reach an LLM endpoint from this environment.

Supported providers (via env):
    LLM_PROVIDER=openai     # OpenAI-compatible chat completions
    LLM_PROVIDER=anthropic  # Anthropic Messages API

Required env vars (see .env.example):
    OPENAI_API_KEY / LLM_BASE_URL / LLM_MODEL
    or ANTHROPIC_API_KEY / ANTHROPIC_MODEL

Usage:
    cp .env.example .env   # then fill in keys
    python examples/llm_smoke_test.py
"""

from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

PROMPT = "Reply with exactly: pong"


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing required environment variable: {name}\n"
            "Copy .env.example to .env and set credentials, or export them."
        )
    return value


def call_openai_compatible() -> str:
    api_key = _require("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": PROMPT},
        ],
        "max_tokens": 32,
        "temperature": 0,
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenAI-compatible response: {data}") from exc


def call_anthropic() -> str:
    api_key = _require("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 32,
        "messages": [
            {"role": "user", "content": PROMPT},
        ],
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    try:
        return data["content"][0]["text"].strip()
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Anthropic response: {data}") from exc


def main() -> int:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    print(f"LLM smoke test — provider={provider}")
    print(f"Prompt: {PROMPT!r}")

    try:
        if provider == "openai":
            text = call_openai_compatible()
        elif provider == "anthropic":
            text = call_anthropic()
        else:
            print(
                f"Unknown LLM_PROVIDER={provider!r}. Use 'openai' or 'anthropic'.",
                file=sys.stderr,
            )
            return 1
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        print(f"HTTP {exc.response.status_code}: {body}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 2

    print("Response:")
    print(text)
    # Helpful when debugging malformed payloads without dumping secrets
    print("\n(ok) smoke test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
