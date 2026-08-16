"""E2E fixtures: full mock site table + SPECS protocol chunks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.rag.chunk import Chunk
from app.rag.store import save_chunks
from tests.e2e.agent_stub import scripted_chat

# Mirrors scripts/create_mock_site_data.py so ranking and edge rows match SPECS.
E2E_SITE_ROWS = [
    ("SITE-001", "Bay Area Research Center", "USA", "North America", 8.3, 2, 24, "Oncology"),
    ("SITE-002", "Midwest Clinical Partners", "USA", "North America", 5.1, 1, 12, "Immunology"),
    ("SITE-003", "Toronto Translational Institute", "Canada", "North America", 6.7, 3, 18, "Oncology"),
    ("SITE-004", "London Early Phase Unit", "UK", "Europe", 4.2, 2, 9, "Neurology"),
    ("SITE-005", "Berlin Academic Medical Center", "Germany", "Europe", 7.0, 4, 30, "Cardiology"),
    ("SITE-006", "Paris Immuno Research Hub", "France", "Europe", 3.8, 1, 6, "Immunology"),
    ("SITE-007", "Tokyo Precision Medicine Clinic", "Japan", "Asia-Pacific", 9.1, 2, 15, "Oncology"),
    ("SITE-008", "Sydney Coastal Trials Network", "Australia", "Asia-Pacific", 2.5, 1, 4, "Respiratory"),
    ("SITE-009", "São Paulo Metro Research Site", "Brazil", "Latin America", 6.0, 2, 20, "Infectious Disease"),
    ("SITE-010", "Seoul University Trial Center", "South Korea", "Asia-Pacific", 7.4, 3, 11, "Oncology"),
    ("SITE-011", "Inactive Desert Site", "USA", "North America", 0.0, 0, 0, "Oncology"),
    ("SITE-012", "Unknown Metrics Site", "Spain", "Europe", None, 1, None, "Neurology"),
]


@pytest.fixture
def e2e_sites_db_path(tmp_path: Path) -> Path:
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
            E2E_SITE_ROWS,
        )
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def e2e_protocols_db_path(tmp_path: Path) -> Path:
    path = tmp_path / "protocols.db"
    save_chunks(
        path,
        [
            Chunk(
                nct_id="NCT04516746",
                section="eligibility.structured",
                text="Minimum age: 18 Years. Maximum age: 75 Years. Healthy volunteers: no.",
                brief_title="Oncology feasibility study",
                start_char=0,
                end_char=69,
                chunk_index=0,
            ),
            Chunk(
                nct_id="NCT04516746",
                section="eligibility.inclusion",
                text=(
                    "Inclusion criteria: histologically confirmed oncology diagnosis; "
                    "ECOG performance status 0-1; measurable disease."
                ),
                brief_title="Oncology feasibility study",
                start_char=0,
                end_char=118,
                chunk_index=0,
            ),
            Chunk(
                nct_id="NCT04516746",
                section="conditions",
                text="Non-small cell lung cancer. Oncology.",
                brief_title="Oncology feasibility study",
                start_char=0,
                end_char=37,
                chunk_index=0,
            ),
        ],
    )
    return path


def _bind_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Settings:
    get_settings.cache_clear()
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.settings", settings)
    return settings


@pytest.fixture
def e2e_settings(
    monkeypatch: pytest.MonkeyPatch,
    e2e_sites_db_path: Path,
    e2e_protocols_db_path: Path,
) -> Settings:
    return _bind_settings(
        monkeypatch,
        Settings(
            sites_db_path=e2e_sites_db_path,
            protocols_db_path=e2e_protocols_db_path,
        ),
    )


@pytest.fixture
def scripted_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic tool-calling model used by the agent loop."""
    monkeypatch.setattr("app.llm.chat", scripted_chat)


@pytest.fixture
def e2e_client(e2e_settings: Settings, scripted_llm: None) -> TestClient:
    return TestClient(app)


@pytest.fixture
def e2e_client_missing_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scripted_llm: None,
) -> TestClient:
    _bind_settings(
        monkeypatch,
        Settings(
            sites_db_path=tmp_path / "missing_sites.db",
            protocols_db_path=tmp_path / "missing_protocols.db",
        ),
    )
    return TestClient(app)


@pytest.fixture
def stub_llm(scripted_llm: None) -> None:
    """Alias kept for SPECS tests that still request stub_llm."""
    return None
