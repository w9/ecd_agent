"""Tests for SQLite protocol chunk storage."""

import sqlite3

from app.rag.chunk import Chunk
from app.rag.store import load_chunks_from_path, save_chunks


def _chunk(**overrides: object) -> Chunk:
    values: dict[str, object] = {
        "nct_id": "NCT00000001",
        "section": "eligibility.inclusion",
        "text": "Age 18 years or older",
        "brief_title": "Toy vaccine study",
        "start_char": 0,
        "end_char": 21,
        "chunk_index": 0,
    }
    values.update(overrides)
    return Chunk(**values)  # type: ignore[arg-type]


def test_save_chunks_assigns_ids_and_round_trips(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    original = [
        _chunk(section="conditions", text="COVID-19", end_char=8, chunk_index=0),
        _chunk(section="design", text="PHASE3", end_char=6, chunk_index=0),
    ]

    stored = save_chunks(db_path, original)
    assert [chunk.id for chunk in stored] == [1, 2]
    assert [(chunk.nct_id, chunk.section, chunk.text) for chunk in stored] == [
        ("NCT00000001", "conditions", "COVID-19"),
        ("NCT00000001", "design", "PHASE3"),
    ]

    reloaded = load_chunks_from_path(db_path)
    assert reloaded == stored


def test_save_chunks_replaces_previous_rows(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(db_path, [_chunk(text="old", end_char=3)])
    stored = save_chunks(db_path, [_chunk(text="new", end_char=3, section="design")])

    assert len(stored) == 1
    assert stored[0].text == "new"
    assert stored[0].section == "design"


def test_schema_is_plain_table_not_fts(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(db_path, [_chunk()])

    conn = sqlite3.connect(db_path)
    try:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'protocol_chunks'"
        ).fetchone()[0]
        fts_tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE '%fts5%'"
        ).fetchall()
    finally:
        conn.close()

    assert "CREATE TABLE" in table_sql
    assert "INTEGER PRIMARY KEY" in table_sql
    assert fts_tables == []
