"""Shared fixtures for the query / routing / site-tool contract tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.rag.chunk import Chunk
from app.rag.store import save_chunks

SITE_ROWS = [
    ("SITE-001", "Bay Area Research Center", "USA", "North America", 8.3, 2, 24, "Oncology"),
    ("SITE-011", "Inactive Desert Site", "USA", "North America", 0.0, 0, 0, "Oncology"),
    ("SITE-012", "Unknown Metrics Site", "Spain", "Europe", None, 1, None, "Neurology"),
]


@pytest.fixture
def sites_db_path(tmp_path: Path) -> Path:
    path = tmp_path / "sites.db"
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
            INSERT INTO sites (
                site_id, site_name, country, region,
                monthly_enrollment_rate, active_trials,
                remaining_slots, therapeutic_area
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            SITE_ROWS,
        )
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def protocols_db_path(tmp_path: Path) -> Path:
    path = tmp_path / "protocols.db"
    save_chunks(
        path,
        [
            Chunk(
                nct_id="NCT00000001",
                section="eligibility.structured",
                text="Minimum age: 18 Years. Healthy volunteers: yes.",
                brief_title="Toy vaccine study",
                start_char=0,
                end_char=47,
                chunk_index=0,
            ),
            Chunk(
                nct_id="NCT00000001",
                section="conditions",
                text="COVID-19, SARS-CoV-2",
                brief_title="Toy vaccine study",
                start_char=0,
                end_char=20,
                chunk_index=0,
            ),
        ],
    )
    return path


@pytest.fixture
def isolated_settings(monkeypatch: pytest.MonkeyPatch, sites_db_path: Path, protocols_db_path: Path) -> Settings:
    settings = Settings(
        sites_db_path=sites_db_path,
        protocols_db_path=protocols_db_path,
    )
    get_settings.cache_clear()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.settings", settings)
    return settings


@pytest.fixture
def client(isolated_settings: Settings) -> TestClient:
    return TestClient(app)
