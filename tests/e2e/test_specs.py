"""End-to-end HTTP contract for SPECS.md.

Black-box tests against GET /health and POST /query. They fail until the
query pipeline is implemented. Protocol/hybrid cases stub the LLM so the
suite stays deterministic; site numbers must still come from the DB.
"""

from __future__ import annotations

import pytest

VALID_ROUTES = {"site", "protocol", "hybrid", "reject"}
VALID_SOURCES = {"sites", "protocol", "hybrid", "none"}


def _post(client, query: str, nct_id: str | None = None):
    return client.post("/query", json={"query": query, "nct_id": nct_id})


def _citation_value(citation: object, key: str) -> object:
    if isinstance(citation, dict):
        return citation.get(key)
    return getattr(citation, key, None)


def _assert_envelope(body: dict) -> None:
    assert set(body) >= {"answer", "route", "source", "citations"}
    assert body["route"] in VALID_ROUTES
    assert body["source"] in VALID_SOURCES
    assert isinstance(body["answer"], str)
    assert isinstance(body["citations"], list)


def _citation_sources(body: dict) -> set[object]:
    return {_citation_value(citation, "source") for citation in body["citations"]}


# --- Health -----------------------------------------------------------------


@pytest.mark.e2e
def test_health_ok(e2e_client) -> None:
    response = e2e_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- In-scope site ----------------------------------------------------------


@pytest.mark.e2e
def test_enrollment_rate_site_001(e2e_client) -> None:
    response = _post(e2e_client, "What is the enrollment rate for SITE-001?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "8.3" in body["answer"]
    assert "SITE-001" in body["answer"]
    assert any(_citation_value(c, "site_id") == "SITE-001" for c in body["citations"])
    assert all(_citation_value(c, "source") == "sites" for c in body["citations"])


@pytest.mark.e2e
def test_active_trials_site_001(e2e_client) -> None:
    response = _post(e2e_client, "How many active trials are at SITE-001?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "2" in body["answer"]
    assert "SITE-001" in body["answer"]


@pytest.mark.e2e
def test_remaining_slots_site_001(e2e_client) -> None:
    response = _post(e2e_client, "How many remaining slots does SITE-001 have?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "24" in body["answer"]


@pytest.mark.e2e
def test_highest_oncology_enrollment_rate_is_site_007(e2e_client) -> None:
    response = _post(e2e_client, "Which oncology site has the highest enrollment rate?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "SITE-007" in body["answer"]
    assert "9.1" in body["answer"]
    invented = {"SITE-013", "SITE-099", "SITE-999"}
    assert invented.isdisjoint(body["answer"].split())


# --- In-scope protocol / hybrid ---------------------------------------------


@pytest.mark.e2e
def test_minimum_age_from_protocol_chunks(e2e_client, stub_llm) -> None:
    response = _post(e2e_client, "What is the minimum age for NCT04516746?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "protocol"
    assert body["source"] == "protocol"
    assert "18" in body["answer"]
    assert body["citations"]
    assert all(_citation_value(c, "nct_id") == "NCT04516746" for c in body["citations"])
    assert all(_citation_value(c, "section") for c in body["citations"])
    assert all(_citation_value(c, "source") == "protocol" for c in body["citations"])
    assert "8.3" not in body["answer"]


@pytest.mark.e2e
def test_inclusion_criteria_with_nct_id_field(e2e_client, stub_llm) -> None:
    response = _post(
        e2e_client,
        "What are the inclusion criteria for this protocol?",
        nct_id="NCT04516746",
    )
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "protocol"
    assert body["source"] == "protocol"
    assert body["citations"]
    assert all(_citation_value(c, "nct_id") == "NCT04516746" for c in body["citations"])
    assert all(_citation_value(c, "section") for c in body["citations"])


@pytest.mark.e2e
def test_hybrid_site_recommendation_cites_both_sources(e2e_client, stub_llm) -> None:
    response = _post(
        e2e_client,
        "Where should I run my next oncology trial given this protocol?",
        nct_id="NCT04516746",
    )
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "hybrid"
    assert body["source"] == "hybrid"
    sources = _citation_sources(body)
    assert "sites" in sources
    assert "protocol" in sources
    assert any(_citation_value(c, "nct_id") == "NCT04516746" for c in body["citations"])
    assert any(
        _citation_value(c, "site_id") in {"SITE-001", "SITE-003", "SITE-007", "SITE-010"}
        for c in body["citations"]
    )


@pytest.mark.e2e
def test_enrollment_criteria_is_eligibility_not_a_site_rate(e2e_client, stub_llm) -> None:
    response = _post(e2e_client, "Enrollment criteria at SITE-001")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "protocol"
    assert "8.3" not in body["answer"]


# --- Unknown / missing data (in-scope, abstain) -----------------------------


@pytest.mark.e2e
def test_unknown_site_yyy_abstains(e2e_client) -> None:
    response = _post(e2e_client, "What is the enrollment rate for site YYY?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    lowered = body["answer"].lower()
    assert "yyy" in lowered
    assert "don't have" in lowered or "do not have" in lowered or "no information" in lowered
    assert "8.3" not in body["answer"]
    assert "9.1" not in body["answer"]


@pytest.mark.e2e
def test_null_rate_site_012_abstains_without_substituting(e2e_client) -> None:
    response = _post(e2e_client, "What is the enrollment rate for SITE-012?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert "8.3" not in body["answer"]
    assert "9.1" not in body["answer"]
    lowered = body["answer"].lower()
    assert (
        "no information" in lowered
        or "don't have" in lowered
        or "do not have" in lowered
        or "not available" in lowered
        or "unknown" in lowered
        or "null" in lowered
        or "missing" in lowered
    )


@pytest.mark.e2e
def test_zero_rate_site_011_is_not_an_unknown_site(e2e_client) -> None:
    response = _post(e2e_client, "What is the enrollment rate for SITE-011?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    lowered = body["answer"].lower()
    reports_zero = "0" in body["answer"]
    reports_unusable = "no usable" in lowered or "not usable" in lowered or "zero" in lowered
    assert reports_zero or reports_unusable
    assert "i don't have any information on site site-011" not in lowered
    assert "i do not have any information on site site-011" not in lowered


@pytest.mark.e2e
def test_empty_retrieval_abstains_with_source_none(e2e_client, stub_llm) -> None:
    response = _post(e2e_client, "What is the dosing schedule for NCT00000001?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "protocol"
    assert body["source"] == "none"
    assert body["citations"] == []
    assert "8.3" not in body["answer"]


# --- Incomplete / ambiguous → 200 reject ------------------------------------


@pytest.mark.e2e
def test_enrollment_rate_without_site_asks_for_site_id(e2e_client) -> None:
    response = _post(e2e_client, "What is the enrollment rate?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    lowered = body["answer"].lower()
    assert "site" in lowered
    assert "8.3" not in body["answer"]
    assert "SITE-001" not in body["answer"]


@pytest.mark.e2e
def test_minimum_age_without_nct_asks_for_nct_id(e2e_client) -> None:
    response = _post(e2e_client, "What is the minimum age?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    lowered = body["answer"].lower()
    assert "nct" in lowered
    assert "18" not in body["answer"]


@pytest.mark.e2e
def test_tell_me_about_the_protocol_asks_which_study(e2e_client) -> None:
    response = _post(e2e_client, "Tell me about the protocol.")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    lowered = body["answer"].lower()
    assert "nct" in lowered or "study" in lowered


@pytest.mark.e2e
def test_tell_me_about_site_001_returns_the_row(e2e_client) -> None:
    response = _post(e2e_client, "Tell me about SITE-001.")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "site"
    assert body["source"] == "sites"
    assert "SITE-001" in body["answer"]
    assert "8.3" in body["answer"]
    assert "2" in body["answer"]
    assert "24" in body["answer"]


# --- Invalid / out of scope -------------------------------------------------


@pytest.mark.e2e
def test_new_protocol_request_is_rejected(e2e_client) -> None:
    response = _post(e2e_client, "Write me a new clinical protocol from scratch")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    assert "8.3" not in body["answer"]
    assert "9.1" not in body["answer"]


@pytest.mark.e2e
def test_medical_advice_is_rejected(e2e_client) -> None:
    response = _post(e2e_client, "Should I enroll my patient in this trial?")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    lowered = body["answer"].lower()
    assert "8.3" not in body["answer"]
    assert "yes" not in lowered.split()


@pytest.mark.e2e
def test_phi_chart_is_rejected(e2e_client) -> None:
    response = _post(e2e_client, "Here is patient John Doe’s chart…")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    assert body["route"] == "reject"
    assert "John Doe" not in body["answer"]


@pytest.mark.e2e
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 8001},
        {"query": "What is the minimum age?", "nct_id": "not-an-id"},
        {"query": "What is the minimum age?", "nct_id": "NCT12"},
        {"query": "What is the minimum age?", "nct_id": "NCTABCDEFGH"},
    ],
)
def test_invalid_request_returns_422(e2e_client, payload: dict) -> None:
    response = e2e_client.post("/query", json=payload)
    assert response.status_code == 422


# --- Failures ---------------------------------------------------------------


@pytest.mark.e2e
def test_llm_down_returns_503_for_every_query(
    e2e_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.llm.chat", boom)

    protocol = _post(e2e_client, "What is the minimum age for NCT04516746?")
    assert protocol.status_code == 503
    protocol_body = protocol.json()
    assert "detail" in protocol_body or "error" in protocol_body

    hybrid = _post(
        e2e_client,
        "Where should I run my next oncology trial given this protocol?",
        nct_id="NCT04516746",
    )
    assert hybrid.status_code == 503

    site = _post(e2e_client, "What is the enrollment rate for SITE-001?")
    assert site.status_code == 503


@pytest.mark.e2e
def test_missing_local_data_abstains_or_returns_503(e2e_client_missing_data) -> None:
    response = _post(e2e_client_missing_data, "What is the enrollment rate for SITE-001?")
    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        _assert_envelope(body)
        lowered = body["answer"].lower()
        assert "8.3" not in body["answer"]
        assert (
            "no information" in lowered
            or "don't have" in lowered
            or "do not have" in lowered
            or "unavailable" in lowered
            or "not available" in lowered
        )
