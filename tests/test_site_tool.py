"""Structured site-data tool contract.

Expected API:
    app.tools.sites.lookup_site(site_id, *, db_path) -> dict | None
    app.tools.sites.get_site_metric(site_id, field, *, db_path) -> number | None

The tool returns records, not prose. Missing or unknown values are None.
"""

import pytest


def test_lookup_site_returns_known_row(sites_db_path) -> None:
    from app.tools.sites import lookup_site

    row = lookup_site("SITE-001", db_path=sites_db_path)
    assert row is not None
    assert row["site_id"] == "SITE-001"
    assert row["site_name"] == "Bay Area Research Center"
    assert row["monthly_enrollment_rate"] == 8.3
    assert row["active_trials"] == 2
    assert row["remaining_slots"] == 24


def test_lookup_site_returns_none_for_unknown_id(sites_db_path) -> None:
    from app.tools.sites import lookup_site

    assert lookup_site("YYY", db_path=sites_db_path) is None
    assert lookup_site("SITE-999", db_path=sites_db_path) is None


@pytest.mark.parametrize(
    ("site_id", "field", "expected"),
    [
        ("SITE-001", "monthly_enrollment_rate", 8.3),
        ("SITE-001", "active_trials", 2),
        ("SITE-001", "remaining_slots", 24),
        ("SITE-011", "monthly_enrollment_rate", 0.0),
        ("SITE-011", "active_trials", 0),
        ("SITE-012", "monthly_enrollment_rate", None),
        ("SITE-012", "remaining_slots", None),
        ("SITE-012", "active_trials", 1),
        ("YYY", "monthly_enrollment_rate", None),
    ],
)
def test_get_site_metric(sites_db_path, site_id: str, field: str, expected: float | int | None) -> None:
    from app.tools.sites import get_site_metric

    assert get_site_metric(site_id, field, db_path=sites_db_path) == expected
