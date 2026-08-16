"""Unit tests for tool dispatch, grounding, and the agent loop."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.agent.assemble import assemble
from app.agent.loop import run_agent
from app.agent.tools import EvidenceLedger, ToolContext, execute_tool
from app.llm import ChatResult, LLMError, ToolCall
from app.rag.chunk import Chunk
from app.rag.store import save_chunks
from app.schemas import QueryRequest
from app.query import handle_query


def _sites_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE sites (
                site_id TEXT PRIMARY KEY,
                site_name TEXT NOT NULL,
                country TEXT,
                region TEXT,
                monthly_enrollment_rate REAL,
                active_trials INTEGER,
                remaining_slots INTEGER,
                therapeutic_area TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO sites VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("SITE-001", "Bay Area", "USA", "NA", 8.3, 2, 24, "Oncology"),
                ("SITE-007", "Tokyo", "Japan", "APAC", 9.1, 2, 15, "Oncology"),
                ("SITE-011", "Inactive", "USA", "NA", 0.0, 0, 0, "Oncology"),
                ("SITE-012", "Unknown", "Spain", "EU", None, 1, None, "Neurology"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _protocols_db(path: Path) -> Path:
    save_chunks(
        path,
        [
            Chunk(
                nct_id="NCT04516746",
                section="eligibility.structured",
                text="Minimum age: 18 Years.",
                brief_title="Oncology feasibility study",
                start_char=0,
                end_char=22,
                chunk_index=0,
            )
        ],
    )
    return path


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        sites_db_path=_sites_db(tmp_path / "sites.db"),
        protocols_db_path=_protocols_db(tmp_path / "protocols.db"),
    )


def test_lookup_site_and_unknown_metric(ctx: ToolContext) -> None:
    found = execute_tool("lookup_site", {"site_id": "SITE-001"}, ctx)
    assert found["found"] is True
    assert found["site"]["monthly_enrollment_rate"] == 8.3

    missing = execute_tool(
        "get_site_metric",
        {"site_id": "YYY", "field": "monthly_enrollment_rate"},
        ctx,
    )
    assert missing == {
        "found": False,
        "site_id": "YYY",
        "field": "monthly_enrollment_rate",
        "value": None,
    }

    null = execute_tool(
        "get_site_metric",
        {"site_id": "SITE-012", "field": "monthly_enrollment_rate"},
        ctx,
    )
    assert null["found"] is True
    assert null["value"] is None


def test_unknown_tool_and_bad_args_are_errors(ctx: ToolContext) -> None:
    assert execute_tool("drop_table", {}, ctx)["error"].startswith("unknown tool")
    assert "error" in execute_tool("get_site_metric", {"site_id": "SITE-001"}, ctx)
    assert "error" in execute_tool(
        "get_site_metric",
        {"site_id": "SITE-001", "field": "password"},
        ctx,
    )


def test_assemble_pins_site_number_and_drops_invented_ids() -> None:
    ledger = EvidenceLedger()
    ledger.used_site_tool = True
    ledger.metric_results.append(
        {
            "found": True,
            "site_id": "SITE-001",
            "field": "monthly_enrollment_rate",
            "value": 8.3,
            "lookup": False,
        }
    )
    response = assemble(
        "What is the enrollment rate for SITE-001?",
        ledger,
        "The monthly enrollment rate for SITE-001 is 99.9. Also SITE-999.",
    )
    assert response.route == "site"
    assert "8.3" in response.answer
    assert "99.9" not in response.answer
    assert "SITE-999" not in response.answer


def test_assemble_no_tools_is_reject() -> None:
    response = assemble("hello", EvidenceLedger(), "The rate is 8.3")
    assert response.route == "reject"
    assert "8.3" not in response.answer


def test_run_agent_uses_tool_results(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    turns = [
        ChatResult(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="get_site_metric",
                    arguments={
                        "site_id": "SITE-001",
                        "field": "monthly_enrollment_rate",
                    },
                )
            ]
        ),
        ChatResult(content="The monthly enrollment rate for SITE-001 is 99.9."),
    ]

    def fake_chat(*args: object, **kwargs: object) -> ChatResult:
        return turns.pop(0)

    monkeypatch.setattr("app.llm.chat", fake_chat)
    response = run_agent(
        "What is the enrollment rate for SITE-001?",
        None,
        sites_db_path=ctx.sites_db_path,
        protocols_db_path=ctx.protocols_db_path,
    )
    assert response.route == "site"
    assert response.source == "sites"
    assert "8.3" in response.answer
    assert response.citations[0].site_id == "SITE-001"
    assert response.llm_debug is None


def test_run_agent_includes_llm_debug(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    turns = [
        ChatResult(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="get_site_metric",
                    arguments={
                        "site_id": "SITE-001",
                        "field": "monthly_enrollment_rate",
                    },
                )
            ],
            debug_request={"model": "debug", "messages": ["turn-1"]},
            debug_response={"id": "resp-1"},
        ),
        ChatResult(
            content="The monthly enrollment rate for SITE-001 is 8.3.",
            debug_request={"model": "debug", "messages": ["turn-2"]},
            debug_response={"id": "resp-2"},
        ),
    ]

    def fake_chat(*args: object, **kwargs: object) -> ChatResult:
        return turns.pop(0)

    monkeypatch.setattr("app.llm.chat", fake_chat)
    response = run_agent(
        "What is the enrollment rate for SITE-001?",
        None,
        sites_db_path=ctx.sites_db_path,
        protocols_db_path=ctx.protocols_db_path,
    )
    assert response.llm_debug is not None
    assert len(response.llm_debug) == 2
    assert response.llm_debug[0].request["messages"] == ["turn-1"]
    assert response.llm_debug[0].response == {"id": "resp-1"}
    assert response.llm_debug[1].request["messages"] == ["turn-2"]


def test_run_agent_debug_cards_snapshot_each_turn(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_chat(messages: list, **kwargs: object) -> ChatResult:
        del kwargs
        live_request = {"messages": messages}
        if any(item.get("role") == "tool" for item in messages):
            return ChatResult(
                content="The monthly enrollment rate for SITE-001 is 8.3.",
                debug_request=live_request,
                debug_response={"id": "resp-2"},
            )
        return ChatResult(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="get_site_metric",
                    arguments={
                        "site_id": "SITE-001",
                        "field": "monthly_enrollment_rate",
                    },
                )
            ],
            debug_request=live_request,
            debug_response={"id": "resp-1"},
        )

    monkeypatch.setattr("app.llm.chat", fake_chat)
    response = run_agent(
        "What is the enrollment rate for SITE-001?",
        None,
        sites_db_path=ctx.sites_db_path,
        protocols_db_path=ctx.protocols_db_path,
    )
    assert response.llm_debug is not None
    assert [item["role"] for item in response.llm_debug[0].request["messages"]] == [
        "system",
        "user",
    ]
    assert [item["role"] for item in response.llm_debug[1].request["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]


def test_run_agent_llm_error_is_not_swallowed(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> ChatResult:
        raise RuntimeError("down")

    monkeypatch.setattr("app.llm.chat", boom)
    with pytest.raises(LLMError):
        handle_query(
            QueryRequest(query="What is the enrollment rate for SITE-001?"),
            sites_db_path=ctx.sites_db_path,
            protocols_db_path=ctx.protocols_db_path,
        )
