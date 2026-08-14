#!/usr/bin/env python3
"""Create synthetic site enrollment CSV + SQLite table for tool-use demos.

Outputs:
    data/sites.csv
    data/sites.db  (table: sites)

All rows are fake. No real patient or company site data is included.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "sites.csv"
DB_PATH = DATA_DIR / "sites.db"

COLUMNS = [
    "site_id",
    "site_name",
    "country",
    "region",
    "monthly_enrollment_rate",
    "active_trials",
    "remaining_slots",
    "therapeutic_area",
]

# Intentionally include missing / zero values for "no information" demos.
SITES: list[dict[str, object]] = [
    {
        "site_id": "SITE-001",
        "site_name": "Bay Area Research Center",
        "country": "USA",
        "region": "North America",
        "monthly_enrollment_rate": 8.3,
        "active_trials": 2,
        "remaining_slots": 24,
        "therapeutic_area": "Oncology",
    },
    {
        "site_id": "SITE-002",
        "site_name": "Midwest Clinical Partners",
        "country": "USA",
        "region": "North America",
        "monthly_enrollment_rate": 5.1,
        "active_trials": 1,
        "remaining_slots": 12,
        "therapeutic_area": "Immunology",
    },
    {
        "site_id": "SITE-003",
        "site_name": "Toronto Translational Institute",
        "country": "Canada",
        "region": "North America",
        "monthly_enrollment_rate": 6.7,
        "active_trials": 3,
        "remaining_slots": 18,
        "therapeutic_area": "Oncology",
    },
    {
        "site_id": "SITE-004",
        "site_name": "London Early Phase Unit",
        "country": "UK",
        "region": "Europe",
        "monthly_enrollment_rate": 4.2,
        "active_trials": 2,
        "remaining_slots": 9,
        "therapeutic_area": "Neurology",
    },
    {
        "site_id": "SITE-005",
        "site_name": "Berlin Academic Medical Center",
        "country": "Germany",
        "region": "Europe",
        "monthly_enrollment_rate": 7.0,
        "active_trials": 4,
        "remaining_slots": 30,
        "therapeutic_area": "Cardiology",
    },
    {
        "site_id": "SITE-006",
        "site_name": "Paris Immuno Research Hub",
        "country": "France",
        "region": "Europe",
        "monthly_enrollment_rate": 3.8,
        "active_trials": 1,
        "remaining_slots": 6,
        "therapeutic_area": "Immunology",
    },
    {
        "site_id": "SITE-007",
        "site_name": "Tokyo Precision Medicine Clinic",
        "country": "Japan",
        "region": "Asia-Pacific",
        "monthly_enrollment_rate": 9.1,
        "active_trials": 2,
        "remaining_slots": 15,
        "therapeutic_area": "Oncology",
    },
    {
        "site_id": "SITE-008",
        "site_name": "Sydney Coastal Trials Network",
        "country": "Australia",
        "region": "Asia-Pacific",
        "monthly_enrollment_rate": 2.5,
        "active_trials": 1,
        "remaining_slots": 4,
        "therapeutic_area": "Respiratory",
    },
    {
        "site_id": "SITE-009",
        "site_name": "São Paulo Metro Research Site",
        "country": "Brazil",
        "region": "Latin America",
        "monthly_enrollment_rate": 6.0,
        "active_trials": 2,
        "remaining_slots": 20,
        "therapeutic_area": "Infectious Disease",
    },
    {
        "site_id": "SITE-010",
        "site_name": "Seoul University Trial Center",
        "country": "South Korea",
        "region": "Asia-Pacific",
        "monthly_enrollment_rate": 7.4,
        "active_trials": 3,
        "remaining_slots": 11,
        "therapeutic_area": "Oncology",
    },
    # Sparse / edge-case rows for guardrail demos
    {
        "site_id": "SITE-011",
        "site_name": "Inactive Desert Site",
        "country": "USA",
        "region": "North America",
        "monthly_enrollment_rate": 0.0,
        "active_trials": 0,
        "remaining_slots": 0,
        "therapeutic_area": "Oncology",
    },
    {
        "site_id": "SITE-012",
        "site_name": "Unknown Metrics Site",
        "country": "Spain",
        "region": "Europe",
        "monthly_enrollment_rate": "",  # missing enrollment rate
        "active_trials": 1,
        "remaining_slots": "",  # missing capacity
        "therapeutic_area": "Neurology",
    },
]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

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

        def to_sql_value(value: object) -> object:
            if value == "" or value is None:
                return None
            return value

        conn.executemany(
            """
            INSERT INTO sites (
                site_id, site_name, country, region,
                monthly_enrollment_rate, active_trials,
                remaining_slots, therapeutic_area
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                tuple(to_sql_value(row[col]) for col in COLUMNS)
                for row in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    write_csv(CSV_PATH, SITES)
    write_sqlite(DB_PATH, SITES)

    print("Created mock site data:")
    print(f"  CSV   : {CSV_PATH} ({len(SITES)} rows)")
    print(f"  SQLite: {DB_PATH} (table: sites, {len(SITES)} rows)")
    print("  Notes : SITE-011 has zero enrollment; SITE-012 has missing metrics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
