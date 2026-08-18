"""Tests for SQLite protocol chunk storage."""

import sqlite3

from app.rag.chunk import Chunk
from app.rag.store import (
    ProtocolDocument,
    extract_json_field,
    load_chunks_from_path,
    save_chunks,
    save_documents,
    search_chunks_from_path,
)


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


def test_fts5_is_separate_external_content_table(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(db_path, [_chunk()])

    conn = sqlite3.connect(db_path)
    try:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'protocol_chunks'"
        ).fetchone()[0]
        fts_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'protocol_chunks_fts'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert "CREATE TABLE" in table_sql
    assert "INTEGER PRIMARY KEY" in table_sql
    assert "USING fts5" in fts_sql
    assert "content='protocol_chunks'" in fts_sql
    assert "content_rowid='id'" in fts_sql


def test_fts5_search_can_scope_to_one_nct(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(
        db_path,
        [
            _chunk(
                nct_id="NCT04368728",
                section="conditions",
                text="RNA vaccine candidate against coronavirus",
                end_char=41,
            ),
            _chunk(
                nct_id="NCT04516746",
                section="conditions",
                text="RNA vaccine is mentioned in an oncology study",
                end_char=45,
            ),
        ],
    )
    hits = search_chunks_from_path(db_path, "vaccine", nct_id="NCT04368728")
    assert [chunk.nct_id for chunk, _rank in hits] == ["NCT04368728"]


def test_fts5_search_ranks_matching_chunk(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(
        db_path,
        [
            _chunk(
                section="interventions",
                text="AZD1222 is a chimpanzee adenovirus vaccine",
                end_char=44,
                chunk_index=0,
            ),
            _chunk(
                section="conditions",
                text="COVID-19, SARS-CoV-2",
                end_char=20,
                chunk_index=0,
            ),
        ],
    )

    hits = search_chunks_from_path(db_path, "AZD1222 adenovirus")
    assert hits
    top, rank = hits[0]
    assert top.section == "interventions"
    assert "AZD1222" in top.text
    assert isinstance(rank, float)


def test_fts5_search_drops_replaced_content(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(db_path, [_chunk(text="cedazuridine with decitabine", end_char=28)])
    save_chunks(db_path, [_chunk(text="mRNA-1273 SARS-CoV-2 vaccine", end_char=28)])

    assert search_chunks_from_path(db_path, "cedazuridine") == []
    hits = search_chunks_from_path(db_path, "vaccine")
    assert len(hits) == 1
    assert "mRNA-1273" in hits[0][0].text


def _document(**overrides: object) -> ProtocolDocument:
    payload: dict[str, object] = {
        "nct_id": "NCT00000001",
        "brief_title": "Toy vaccine study",
        "document": {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT00000001",
                    "briefTitle": "Toy vaccine study",
                },
                "eligibilityModule": {
                    "minimumAge": "18 Years",
                    "healthyVolunteers": True,
                    "stdAges": ["ADULT", "OLDER_ADULT"],
                },
            }
        },
    }
    payload.update(overrides)
    return ProtocolDocument(**payload)  # type: ignore[arg-type]


def test_save_documents_round_trips_and_extracts_nested_fields(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_documents(db_path, [_document()])

    rows = extract_json_field(
        db_path, "$.protocolSection.eligibilityModule.minimumAge"
    )
    assert rows == [
        {
            "nct_id": "NCT00000001",
            "path": "$.protocolSection.eligibilityModule.minimumAge",
            "found": True,
            "value": "18 Years",
            "json_type": "text",
        }
    ]

    ages = extract_json_field(
        db_path, "$.protocolSection.eligibilityModule.stdAges"
    )
    assert ages[0]["found"] is True
    assert ages[0]["value"] == ["ADULT", "OLDER_ADULT"]
    assert ages[0]["json_type"] == "array"


def test_extract_json_field_can_scope_or_miss(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_documents(
        db_path,
        [
            _document(),
            _document(
                nct_id="NCT04516746",
                brief_title="Other",
                document={
                    "protocolSection": {
                        "eligibilityModule": {"minimumAge": "21 Years"},
                    }
                },
            ),
        ],
    )

    scoped = extract_json_field(
        db_path,
        "$.protocolSection.eligibilityModule.minimumAge",
        nct_id="nct04516746",
    )
    assert [row["nct_id"] for row in scoped] == ["NCT04516746"]
    assert scoped[0]["value"] == "21 Years"

    missing = extract_json_field(
        db_path, "$.protocolSection.designModule.phases", nct_id="NCT00000001"
    )
    assert missing[0]["found"] is False
    assert missing[0]["value"] is None

    unknown = extract_json_field(
        db_path, "$.protocolSection.eligibilityModule.minimumAge", nct_id="NCT99999999"
    )
    assert unknown == []
