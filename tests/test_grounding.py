"""Grounding and abstention contract for assembled answers.

Expected API:
    app.query.handle_query(request, *, sites_db_path=None, protocols_db_path=None)
        -> object with .answer, .route, .source, .citations
    app.schemas.QueryRequest(query: str, nct_id: str | None = None)
    app.grounding.must_abstain(hits, tool_result) -> bool
    app.grounding.grounded_citations(citations, hits) -> list
    app.llm.complete(...)  (patched in these tests)
"""

from __future__ import annotations

import pytest


def _citation_value(citation: object, key: str) -> object:
    if isinstance(citation, dict):
        return citation.get(key)
    return getattr(citation, key, None)


def test_must_abstain_when_no_evidence() -> None:
    from app.grounding import must_abstain

    assert must_abstain(hits=[], tool_result=None) is True


def test_must_not_abstain_when_hits_exist() -> None:
    from app.grounding import must_abstain

    assert must_abstain(hits=[{"nct_id": "NCT00000001"}], tool_result=None) is False


def test_must_not_abstain_when_tool_result_exists() -> None:
    from app.grounding import must_abstain

    assert must_abstain(hits=[], tool_result={"monthly_enrollment_rate": 8.3}) is False


def test_grounded_citations_drop_ids_not_in_hits() -> None:
    from app.grounding import grounded_citations

    hits = [{"nct_id": "NCT00000001", "section": "eligibility.structured"}]
    citations = [
        {"source": "protocol", "nct_id": "NCT00000001", "section": "eligibility.structured"},
        {"source": "protocol", "nct_id": "NCT99999999", "section": "design"},
    ]
    kept = grounded_citations(citations, hits)
    assert len(kept) == 1
    assert _citation_value(kept[0], "nct_id") == "NCT00000001"
    assert _citation_value(kept[0], "section") == "eligibility.structured"


def test_handle_query_abstains_when_retrieval_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    sites_db_path,
    protocols_db_path,
) -> None:
    from app.query import handle_query
    from app.schemas import QueryRequest

    monkeypatch.setattr("app.rag.store.search_chunks_from_path", lambda *args, **kwargs: [])
    result = handle_query(
        QueryRequest(query="What is the dosing schedule for NCT00000001?", nct_id="NCT00000001"),
        sites_db_path=sites_db_path,
        protocols_db_path=protocols_db_path,
    )
    assert result.citations == []
    assert result.source == "none"
    assert "8.3" not in result.answer
    lowered = result.answer.lower()
    assert "no information" in lowered or "don't have" in lowered or "do not have" in lowered


def test_structured_answer_cannot_use_a_number_absent_from_the_tool(
    monkeypatch: pytest.MonkeyPatch,
    sites_db_path,
    protocols_db_path,
) -> None:
    from app.query import handle_query
    from app.schemas import QueryRequest

    monkeypatch.setattr("app.llm.complete", lambda *args, **kwargs: "The monthly enrollment rate is 99.9.")
    result = handle_query(
        QueryRequest(query="What is the enrollment rate for SITE-001?"),
        sites_db_path=sites_db_path,
        protocols_db_path=protocols_db_path,
    )
    assert result.route == "site"
    assert result.source == "sites"
    assert "8.3" in result.answer
    assert "99.9" not in result.answer
    assert any(_citation_value(citation, "site_id") == "SITE-001" for citation in result.citations)
