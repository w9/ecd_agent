"""HTTP contract for POST /query.

Expected request:  {"query": str, "nct_id": str | None}
Expected response: {"answer", "route", "source", "citations"}

Routes: site | protocol | hybrid | reject
Sources: sites | protocol | hybrid | none
"""

from __future__ import annotations

import pytest


def _citation_value(citation: object, key: str) -> object:
    if isinstance(citation, dict):
        return citation.get(key)
    return getattr(citation, key, None)


def test_enrollment_rate_for_known_site(client) -> None:
    response = client.post("/query", json={"query": "What is the enrollment rate for SITE-001?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "8.3" in body["answer"]
    assert any(_citation_value(citation, "site_id") == "SITE-001" for citation in body["citations"])


def test_unknown_site_abstains_without_inventing_a_rate(client) -> None:
    response = client.post("/query", json={"query": "What is the enrollment rate for site YYY?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "site"
    lowered = body["answer"].lower()
    assert "no information" in lowered or "don't have" in lowered or "do not have" in lowered
    assert "8.3" not in body["answer"]


def test_zero_enrollment_site_is_reported_as_no_usable_rate(client) -> None:
    response = client.post("/query", json={"query": "What is the enrollment rate for SITE-011?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "site"
    lowered = body["answer"].lower()
    assert "no information" in lowered or "don't have" in lowered or "do not have" in lowered or "0" in body["answer"]


def test_missing_enrollment_metric_abstains(client) -> None:
    response = client.post("/query", json={"query": "What is the enrollment rate for SITE-012?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "site"
    lowered = body["answer"].lower()
    assert "no information" in lowered or "don't have" in lowered or "do not have" in lowered
    assert "8.3" not in body["answer"]


def test_active_trials_for_known_site(client) -> None:
    response = client.post("/query", json={"query": "How many active trials are at SITE-001?"})
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "2" in body["answer"]


def test_protocol_query_returns_grounded_citations(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.llm.complete", lambda *args, **kwargs: "The minimum age is 18 years.")
    response = client.post(
        "/query",
        json={"query": "What is the minimum age for NCT00000001?", "nct_id": "NCT00000001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "protocol"
    assert body["source"] == "protocol"
    assert body["citations"]
    assert all(_citation_value(citation, "nct_id") == "NCT00000001" for citation in body["citations"])
    assert all(_citation_value(citation, "section") for citation in body["citations"])
    assert all(_citation_value(citation, "source") == "protocol" for citation in body["citations"])


def test_hybrid_recommendation_cites_sites_and_protocol(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.llm.complete",
        lambda *args, **kwargs: "SITE-001 is a strong oncology match for this protocol.",
    )
    response = client.post(
        "/query",
        json={
            "query": "Where should I run my next oncology trial given this protocol?",
            "nct_id": "NCT00000001",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "hybrid"
    assert body["source"] == "hybrid"
    sources = {_citation_value(citation, "source") for citation in body["citations"]}
    assert "sites" in sources
    assert "protocol" in sources


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 8001},
        {"query": "What is the minimum age?", "nct_id": "not-an-id"},
    ],
)
def test_invalid_payload_returns_422(client, payload: dict) -> None:
    response = client.post("/query", json=payload)
    assert response.status_code == 422


def test_rejected_query_does_not_invent_site_metrics(client) -> None:
    response = client.post("/query", json={"query": "Write me a new clinical protocol from scratch"})
    assert response.status_code in {200, 400, 422}
    if response.status_code == 200:
        body = response.json()
        assert body["route"] == "reject"
        assert "8.3" not in body["answer"]


def test_llm_failure_on_protocol_query_returns_503(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.llm.complete", boom)
    response = client.post(
        "/query",
        json={"query": "What is the minimum age for NCT00000001?", "nct_id": "NCT00000001"},
    )
    assert response.status_code == 503
    body = response.json()
    assert "detail" in body or "error" in body
