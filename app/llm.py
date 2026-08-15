"""OpenRouter chat completions used for protocol and hybrid answers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

from app.config import PROJECT_ROOT, get_settings

DEFAULT_MODEL = "openai/gpt-5.6-luna"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
KEY_FILE = PROJECT_ROOT / ".secrets" / "openrouter_key"


class LLMError(RuntimeError):
    """Raised when the upstream model cannot be reached or returns garbage."""


def complete(prompt: str, *, system: str | None = None) -> str:
    """Return model text. Tests patch this function for determinism."""
    settings = get_settings()
    api_key = _api_key()
    if not api_key:
        raise LLMError("OpenRouter API key is not configured")

    base_url = (settings.llm_base_url or DEFAULT_BASE_URL).rstrip("/")
    model = settings.llm_model or DEFAULT_MODEL
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024,
    }
    if settings.llm_debug:
        print("=== LLM request ===", file=sys.stderr, flush=True)
        print(json.dumps(body, indent=2), file=sys.stderr, flush=True)
        print("=== end LLM request ===", file=sys.stderr, flush=True)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://openrouter.ai",
                    "X-OpenRouter-Title": "clinical-site-feasibility",
                },
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMError("LLM unavailable") from exc

    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM unavailable") from exc
    if not isinstance(text, str) or not text.strip():
        raise LLMError("LLM unavailable")
    return text.strip()


def _api_key() -> str:
    settings = get_settings()
    for candidate in (
        settings.openrouter_api_key,
        settings.openai_api_key,
        _read_key_file(KEY_FILE),
    ):
        if candidate:
            return candidate
    return ""


def _read_key_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
