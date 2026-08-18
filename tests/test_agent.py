"""Unit tests for tool dispatch and the agent loop."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.agent.loop import run_agent
from app.agent.tools import ToolContext, execute_tool
from app.llm import ChatResult, LLMError, ToolCall
from app.rag.chunk import Chunk
from app.rag.store import ProtocolDocument, save_chunks, save_documents
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


def _protocol_docs(path: Path) -> Path:
    save_documents(
        path,
        [
            ProtocolDocument(
                nct_id="NCT04516746",
                brief_title="Oncology feasibility study",
                document={
                    "protocolSection": {
                        "eligibilityModule": {"minimumAge": "18 Years", "sex": "ALL"},
                    }
                },
            )
        ],
    )
    return path


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        sites_db_path=_sites_db(tmp_path / "sites.db"),
        protocols_db_path=_protocol_docs(_protocols_db(tmp_path / "protocols.db")),
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


def test_respond_returns_the_model_envelope(ctx: ToolContext) -> None:
    payload = execute_tool(
        "respond",
        {
            "answer": "SITE-011 has the lowest enrollment rate at 0.0.",
            "route": "site",
            "source": "sites",
            "citations": [{"source": "sites", "site_id": "SITE-011"}],
        },
        ctx,
    )
    assert payload["submitted"] is True
    assert payload["answer"] == "SITE-011 has the lowest enrollment rate at 0.0."
    assert payload["route"] == "site"
    assert payload["citations"][0]["site_id"] == "SITE-011"


def test_search_protocol_reports_unscoped_and_not_site_bound(ctx: ToolContext) -> None:
    result = execute_tool(
        "search_protocol",
        {"query": "Enrollment criteria at SITE-001", "nct_id": ""},
        ctx,
    )
    assert result["scoped_to_nct"] is False
    assert result["nct_id"] is None
    assert result["site_bound"] is False
    assert "site" in result["note"].lower()


def test_search_protocol_reports_scoped_when_nct_passed(ctx: ToolContext) -> None:
    result = execute_tool(
        "search_protocol",
        {"query": "minimum age", "nct_id": "NCT04516746"},
        ctx,
    )
    assert result["scoped_to_nct"] is True
    assert result["nct_id"] == "NCT04516746"
    assert result["chunks"]


def test_get_protocol_field_and_filter_sites_dispatch(ctx: ToolContext) -> None:
    field = execute_tool(
        "get_protocol_field",
        {
            "path": "protocolSection.eligibilityModule.minimumAge",
            "nct_id": "NCT04516746",
        },
        ctx,
    )
    assert field["scoped_to_nct"] is True
    assert field["results"][0]["value"] == "18 Years"

    page = execute_tool(
        "filter_sites",
        {
            "filters": [
                {"field": "therapeutic_area", "op": "eq", "value": "Oncology"},
                {"field": "monthly_enrollment_rate", "op": "gt", "value": 8},
            ],
            "offset": 0,
            "limit": 5,
        },
        ctx,
    )
    assert [row["site_id"] for row in page["sites"]] == ["SITE-001", "SITE-007"]
    assert page["total"] == 2
    assert page["has_more"] is False


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
        ChatResult(
            tool_calls=[
                ToolCall(
                    id="c2",
                    name="respond",
                    arguments={
                        "answer": "The monthly enrollment rate for SITE-001 is 8.3.",
                        "route": "site",
                        "source": "sites",
                        "citations": [{"source": "sites", "site_id": "SITE-001"}],
                    },
                )
            ]
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
    assert response.route == "site"
    assert response.source == "sites"
    assert "8.3" in response.answer
    assert response.citations[0].site_id == "SITE-001"
    assert response.llm_debug is None


def test_run_agent_does_not_rewrite_respond_payload(
    ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        ChatResult(
            tool_calls=[
                ToolCall(
                    id="c2",
                    name="respond",
                    arguments={
                        "answer": "SITE-011 has the lowest enrollment rate at 0.0.",
                        "route": "site",
                        "source": "sites",
                        "citations": [{"source": "sites", "site_id": "SITE-011"}],
                    },
                )
            ]
        ),
    ]

    def fake_chat(*args: object, **kwargs: object) -> ChatResult:
        return turns.pop(0)

    monkeypatch.setattr("app.llm.chat", fake_chat)
    response = run_agent(
        "Which site has the lowest enrollment rate?",
        None,
        sites_db_path=ctx.sites_db_path,
        protocols_db_path=ctx.protocols_db_path,
    )
    assert response.answer == "SITE-011 has the lowest enrollment rate at 0.0."
    assert response.route == "site"
    assert response.source == "sites"
    assert response.citations[0].site_id == "SITE-011"


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
            tool_calls=[
                ToolCall(
                    id="c2",
                    name="respond",
                    arguments={
                        "answer": "The monthly enrollment rate for SITE-001 is 8.3.",
                        "route": "site",
                        "source": "sites",
                        "citations": [{"source": "sites", "site_id": "SITE-001"}],
                    },
                )
            ],
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
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="respond",
                        arguments={
                            "answer": "The monthly enrollment rate for SITE-001 is 8.3.",
                            "route": "site",
                            "source": "sites",
                            "citations": [{"source": "sites", "site_id": "SITE-001"}],
                        },
                    )
                ],
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
