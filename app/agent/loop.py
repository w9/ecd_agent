"""Agentic loop: the model chooses tools, then we ground the answer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import app.llm as llm
from app.agent.assemble import assemble, should_short_circuit
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_SCHEMAS, EvidenceLedger, ToolContext, execute_tool
from app.llm import ChatResult, LLMError
from app.schemas import QueryResponse

MAX_STEPS = 6


def run_agent(
    query: str,
    nct_id: str | None,
    *,
    sites_db_path: Path | str,
    protocols_db_path: Path | str,
) -> QueryResponse:
    ctx = ToolContext(sites_db_path=sites_db_path, protocols_db_path=protocols_db_path)
    ledger = EvidenceLedger()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_message(query, nct_id)},
    ]

    for _ in range(MAX_STEPS):
        result = _step(messages)
        if result.tool_calls:
            messages.append(result.as_message())
            for call in result.tool_calls:
                payload = execute_tool(call.name, call.arguments, ctx)
                ledger.record(call.name, payload)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(payload, default=str),
                    }
                )
            if should_short_circuit(ledger):
                return assemble(query, ledger, None)
            continue
        return assemble(query, ledger, result.content)

    return assemble(query, ledger, None)


def _step(messages: list[dict[str, Any]]) -> ChatResult:
    try:
        return llm.chat(messages, tools=TOOL_SCHEMAS)
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError("LLM unavailable") from exc


def _user_message(query: str, nct_id: str | None) -> str:
    if nct_id:
        return f"User question: {query}\nAttached NCT ID: {nct_id}"
    return f"User question: {query}"
