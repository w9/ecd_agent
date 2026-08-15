"""Input validation contract for the query API.

Expected API:
    app.validation.validate_query(query, nct_id=None) -> cleaned query str
    app.validation.QueryValidationError  (raised on invalid input)
    app.validation.MAX_QUERY_LENGTH == 8000
"""

import pytest


def test_validate_query_accepts_plain_text() -> None:
    from app.validation import validate_query

    assert validate_query("What is the enrollment rate for SITE-001?") == (
        "What is the enrollment rate for SITE-001?"
    )


def test_validate_query_strips_whitespace() -> None:
    from app.validation import validate_query

    assert validate_query("  How many active trials are at SITE-001?  ") == (
        "How many active trials are at SITE-001?"
    )


def test_validate_query_normalizes_nct_id() -> None:
    from app.validation import validate_query

    cleaned = validate_query("What is the minimum age?", nct_id="nct00000001")
    assert cleaned == "What is the minimum age?"


@pytest.mark.parametrize("query", ["", "   ", None])
def test_validate_query_rejects_empty(query: str | None) -> None:
    from app.validation import QueryValidationError, validate_query

    with pytest.raises(QueryValidationError):
        validate_query(query)


def test_validate_query_rejects_oversized_payload() -> None:
    from app.validation import MAX_QUERY_LENGTH, QueryValidationError, validate_query

    with pytest.raises(QueryValidationError):
        validate_query("x" * (MAX_QUERY_LENGTH + 1))


@pytest.mark.parametrize("nct_id", ["not-an-id", "NCT12", "NCTABCDEFGH"])
def test_validate_query_rejects_malformed_nct_id(nct_id: str) -> None:
    from app.validation import QueryValidationError, validate_query

    with pytest.raises(QueryValidationError):
        validate_query("What is the minimum age?", nct_id=nct_id)
