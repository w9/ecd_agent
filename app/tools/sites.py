"""Read-only lookups against the mock sites SQLite table."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SITE_FIELDS = (
    "site_id",
    "site_name",
    "country",
    "region",
    "monthly_enrollment_rate",
    "active_trials",
    "remaining_slots",
    "therapeutic_area",
)


def lookup_site(site_id: str, *, db_path: Path | str) -> dict[str, Any] | None:
    """Return one site row, or None if the id or database is missing."""
    row = _fetch_one(
        db_path,
        "SELECT * FROM sites WHERE site_id = ? COLLATE NOCASE",
        (site_id,),
    )
    return _normalize(row) if row is not None else None


def get_site_metric(site_id: str, field: str, *, db_path: Path | str) -> float | int | None:
    """Return a single numeric field. Missing/unknown values are None."""
    if field not in SITE_FIELDS:
        raise ValueError(f"unsupported site field: {field}")
    row = lookup_site(site_id, db_path=db_path)
    if row is None:
        return None
    return row.get(field)


def list_sites(
    *,
    db_path: Path | str,
    therapeutic_area: str | None = None,
) -> list[dict[str, Any]]:
    """Return site rows, optionally filtered by therapeutic area."""
    if therapeutic_area:
        rows = _fetch_all(
            db_path,
            "SELECT * FROM sites WHERE therapeutic_area = ? COLLATE NOCASE",
            (therapeutic_area,),
        )
    else:
        rows = _fetch_all(db_path, "SELECT * FROM sites", ())
    return [_normalize(row) for row in rows]


def rank_sites(
    *,
    db_path: Path | str,
    field: str = "monthly_enrollment_rate",
    therapeutic_area: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank sites by a numeric field, skipping nulls."""
    if field not in SITE_FIELDS:
        raise ValueError(f"unsupported site field: {field}")
    sites = [
        row
        for row in list_sites(db_path=db_path, therapeutic_area=therapeutic_area)
        if row.get(field) is not None
    ]
    sites.sort(key=lambda row: row[field], reverse=True)
    return sites[:limit]


def _connect(db_path: Path | str) -> sqlite3.Connection | None:
    path = Path(db_path)
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error:
        return None
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_one(db_path: Path | str, sql: str, params: tuple[object, ...]) -> sqlite3.Row | None:
    conn = _connect(db_path)
    if conn is None:
        return None
    try:
        return conn.execute(sql, params).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _fetch_all(db_path: Path | str, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
    conn = _connect(db_path)
    if conn is None:
        return []
    try:
        return list(conn.execute(sql, params).fetchall())
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _normalize(row: sqlite3.Row) -> dict[str, Any]:
    data = {key: row[key] for key in row.keys() if key in SITE_FIELDS}
    if "site_id" in data and isinstance(data["site_id"], str):
        data["site_id"] = data["site_id"].upper()
    return data
