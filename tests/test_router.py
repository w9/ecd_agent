"""Router contract: classify free-text queries before retrieval or tool use.

Expected API:
    app.routing.classify(query) -> object with .route in
        {"site", "protocol", "hybrid", "reject"}
    app.routing.extract_site_id(query) -> str | None
    app.routing.extract_metric_field(query) -> str | None
"""

import pytest


@pytest.mark.parametrize(
    ("query", "route"),
    [
        ("What is the enrollment rate for SITE-001?", "site"),
        ("How many active trials are at SITE-001?", "site"),
        ("What is the enrollment rate for site YYY?", "site"),
        ("What is the minimum age for NCT00000001?", "protocol"),
        ("What are the inclusion criteria for this protocol?", "protocol"),
        ("Where should I run my next oncology trial?", "hybrid"),
        ("Write me a new clinical protocol from scratch", "reject"),
        ("enrollment criteria at SITE-001", "protocol"),
    ],
)
def test_classify_routes_example_queries(query: str, route: str) -> None:
    from app.routing import classify

    assert classify(query).route == route


@pytest.mark.parametrize(
    ("query", "site_id"),
    [
        ("What is the enrollment rate for SITE-001?", "SITE-001"),
        ("How many active trials are at site SITE-011?", "SITE-011"),
        ("What is the enrollment rate for site YYY?", "YYY"),
        ("What is the minimum age for NCT00000001?", None),
    ],
)
def test_extract_site_id(query: str, site_id: str | None) -> None:
    from app.routing import extract_site_id

    assert extract_site_id(query) == site_id


@pytest.mark.parametrize(
    ("query", "field"),
    [
        ("What is the enrollment rate for SITE-001?", "monthly_enrollment_rate"),
        ("How many active trials are at SITE-001?", "active_trials"),
        ("How many remaining slots does SITE-001 have?", "remaining_slots"),
        ("What is the minimum age for NCT00000001?", None),
    ],
)
def test_extract_metric_field(query: str, field: str | None) -> None:
    from app.routing import extract_metric_field

    assert extract_metric_field(query) == field
