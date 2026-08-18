"""Tests for site lookup, ranking, and filtered paging."""

from pathlib import Path

import sqlite3

from app.tools.sites import filter_sites, list_sites


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
            "INSERT INTO sites VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("SITE-001", "Bay Area", "USA", "North America", 8.3, 2, 24, "Oncology"),
                ("SITE-003", "Toronto", "Canada", "North America", 6.7, 3, 18, "Oncology"),
                ("SITE-007", "Tokyo", "Japan", "Asia-Pacific", 9.1, 2, 15, "Oncology"),
                ("SITE-011", "Inactive", "USA", "North America", 0.0, 0, 0, "Oncology"),
                ("SITE-012", "Unknown", "Spain", "Europe", None, 1, None, "Neurology"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return path


def test_filter_sites_and_pagination(tmp_path: Path) -> None:
    db_path = _sites_db(tmp_path / "sites.db")
    page = filter_sites(
        db_path=db_path,
        filters=[
            {"field": "therapeutic_area", "op": "eq", "value": "Oncology"},
            {"field": "monthly_enrollment_rate", "op": "gte", "value": 6},
        ],
        offset=0,
        limit=2,
    )
    assert page["total"] == 3
    assert page["has_more"] is True
    assert [row["site_id"] for row in page["sites"]] == ["SITE-001", "SITE-003"]

    next_page = filter_sites(
        db_path=db_path,
        filters=[
            {"field": "therapeutic_area", "op": "eq", "value": "oncology"},
            {"field": "monthly_enrollment_rate", "op": "gte", "value": 6},
        ],
        offset=2,
        limit=2,
    )
    assert [row["site_id"] for row in next_page["sites"]] == ["SITE-007"]
    assert next_page["has_more"] is False


def test_filter_sites_rejects_compare_on_categorical(tmp_path: Path) -> None:
    db_path = _sites_db(tmp_path / "sites.db")
    try:
        filter_sites(
            db_path=db_path,
            filters=[{"field": "country", "op": "gt", "value": "USA"}],
        )
    except ValueError as exc:
        assert "only supports op=eq" in str(exc)
    else:
        raise AssertionError("expected categorical compare to raise")


def test_list_sites_still_filters_therapeutic_area(tmp_path: Path) -> None:
    db_path = _sites_db(tmp_path / "sites.db")
    rows = list_sites(db_path=db_path, therapeutic_area="Neurology")
    assert [row["site_id"] for row in rows] == ["SITE-012"]
