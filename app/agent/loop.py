"""Agentic loop: the model chooses tools, then we ground the answer."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import app.llm as llm
from app.agent.assemble import assemble
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_SCHEMAS, EvidenceLedger, ToolContext, execute_tool
from app.llm import ChatResult, LLMError
from app.schemas import LlmDebugExchange, QueryResponse

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
    debug_turns: list[LlmDebugExchange] = []
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_message(query, nct_id)},
    ]

    def finish(response: QueryResponse) -> QueryResponse:
        if not debug_turns:
            return response
        return response.model_copy(update={"llm_debug": debug_turns})

    for _ in range(MAX_STEPS):
        result = _step(messages)
        _capture_debug(debug_turns, result)
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
            continue
        return finish(assemble(query, ledger, result.content))

    return finish(assemble(query, ledger, None))


def _capture_debug(debug_turns: list[LlmDebugExchange], result: ChatResult) -> None:
    if result.debug_request is None:
        return
    # Snapshot now. The loop appends tool results to `messages` next, and
    # debug_request may still alias that live list.
    debug_turns.append(
        LlmDebugExchange(
            request=copy.deepcopy(result.debug_request),
            response=copy.deepcopy(result.debug_response or {}),
        )
    )


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
