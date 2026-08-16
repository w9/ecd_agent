"""OpenRouter chat completions used by the feasibility agent."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import PROJECT_ROOT, get_settings

DEFAULT_MODEL = "openai/gpt-5.6-luna"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
KEY_FILE = PROJECT_ROOT / ".secrets" / "openrouter_key"


class LLMError(RuntimeError):
    """Raised when the upstream model cannot be reached or returns garbage."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict[str, Any]:
        """OpenAI-compatible assistant message to append to the transcript."""
        message: dict[str, Any] = {
            "role": "assistant",
            "content": self.content,
        }
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in self.tool_calls
            ]
        return message


def complete(prompt: str, *, system: str | None = None) -> str:
    """Return model text. Tests patch this function for determinism."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    result = chat(messages)
    if not result.content or not result.content.strip():
        raise LLMError("LLM unavailable")
    return result.content.strip()


def chat(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> ChatResult:
    """One chat-completions turn. May return tool calls, text, or both."""
    settings = get_settings()
    api_key = _api_key()
    if not api_key:
        raise LLMError("OpenRouter API key is not configured")

    base_url = (settings.llm_base_url or DEFAULT_BASE_URL).rstrip("/")
    model = settings.llm_model or DEFAULT_MODEL
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

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
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM unavailable") from exc

    content = message.get("content")
    if content is not None and not isinstance(content, str):
        content = str(content)
    if isinstance(content, str):
        content = content.strip() or None

    tool_calls = _parse_tool_calls(message.get("tool_calls"))
    if not tool_calls and (not content or not content.strip()):
        raise LLMError("LLM unavailable")
    return ChatResult(content=content, tool_calls=tool_calls)


def _parse_tool_calls(raw: object) -> list[ToolCall]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise LLMError("LLM unavailable")
    parsed: list[ToolCall] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise LLMError("LLM unavailable")
        function = item.get("function")
        if not isinstance(function, dict):
            raise LLMError("LLM unavailable")
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            raise LLMError("LLM unavailable")
        arguments = _parse_arguments(function.get("arguments"))
        call_id = item.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"call_{index}_{uuid4().hex[:8]}"
        parsed.append(ToolCall(id=call_id, name=name.strip(), arguments=arguments))
    return parsed


def _parse_arguments(raw: object) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise LLMError("LLM unavailable")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM unavailable") from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise LLMError("LLM unavailable")
    return parsed


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
