"""Tests for unscoped protocol search rewriting and eligibility filtering."""

from pathlib import Path

from app.rag.chunk import Chunk
from app.rag.store import ProtocolDocument, save_chunks, save_documents
from app.tools.protocols import get_protocol_field, is_eligibility_query, search_protocol


def _chunk(**overrides: object) -> Chunk:
    values: dict[str, object] = {
        "nct_id": "NCT04470427",
        "section": "eligibility.inclusion",
        "text": "Healthy adults or adults with stable pre-existing medical conditions.",
        "brief_title": "mRNA-1273 COVID-19 vaccine study",
        "start_char": 0,
        "end_char": 68,
        "chunk_index": 0,
    }
    values.update(overrides)
    return Chunk(**values)  # type: ignore[arg-type]


def _db(path: Path) -> Path:
    save_chunks(
        path,
        [
            _chunk(),
            _chunk(
                nct_id="NCT04368728",
                text="Healthy participants determined eligible by the investigator.",
                end_char=60,
            ),
            _chunk(
                nct_id="NCT04156698",
                section="design",
                text="Study type: INTERVENTIONAL. Enrollment: 51 (ESTIMATED).",
                brief_title="Unrelated hypopharyngeal study",
                end_char=55,
            ),
            _chunk(
                nct_id="NCT04516746",
                section="conditions",
                text="Non-small cell lung cancer. Oncology.",
                brief_title="Oncology feasibility study",
                end_char=37,
            ),
        ],
    )
    return path


def test_enrollment_criteria_is_an_eligibility_query() -> None:
    assert is_eligibility_query("Enrollment criteria at SITE-001")
    assert is_eligibility_query("What are the inclusion criteria?")
    assert not is_eligibility_query("What is the enrollment rate for SITE-001?")


def test_unscoped_eligibility_search_drops_design_enrollment(tmp_path: Path) -> None:
    db_path = _db(tmp_path / "protocols.db")
    chunks = search_protocol("Enrollment criteria at SITE-001", db_path=db_path)

    assert chunks
    assert all(chunk["section"].startswith("eligibility.") for chunk in chunks)
    assert {chunk["nct_id"] for chunk in chunks} == {"NCT04470427", "NCT04368728"}
    assert not any("51" in chunk["text"] for chunk in chunks)
    assert not any(chunk["section"] == "design" for chunk in chunks)


def test_unscoped_scientific_search_uses_and_and_ignores_site_id(tmp_path: Path) -> None:
    db_path = _db(tmp_path / "protocols.db")
    chunks = search_protocol("lung cancer at SITE-001", db_path=db_path)

    assert [chunk["nct_id"] for chunk in chunks] == ["NCT04516746"]
    assert chunks[0]["section"] == "conditions"


def test_get_protocol_field_reads_nested_json_and_all_studies(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_documents(
        db_path,
        [
            ProtocolDocument(
                nct_id="NCT00000001",
                brief_title="Toy",
                document={
                    "protocolSection": {
                        "eligibilityModule": {"minimumAge": "18 Years", "sex": "ALL"},
                    }
                },
            ),
            ProtocolDocument(
                nct_id="NCT04516746",
                brief_title="Oncology",
                document={
                    "protocolSection": {
                        "eligibilityModule": {"minimumAge": "21 Years", "sex": "ALL"},
                    }
                },
            ),
        ],
    )

    scoped = get_protocol_field(
        "protocolSection.eligibilityModule.minimumAge",
        db_path=db_path,
        nct_id="nct04516746",
    )
    assert scoped["path"] == "$.protocolSection.eligibilityModule.minimumAge"
    assert scoped["scoped_to_nct"] is True
    assert scoped["results"][0]["value"] == "21 Years"

    unscoped = get_protocol_field(
        "$.protocolSection.eligibilityModule.minimumAge",
        db_path=db_path,
    )
    assert unscoped["scoped_to_nct"] is False
    assert [row["nct_id"] for row in unscoped["results"]] == [
        "NCT00000001",
        "NCT04516746",
    ]
    assert [row["value"] for row in unscoped["results"]] == ["18 Years", "21 Years"]

    missing = get_protocol_field(
        "$.protocolSection.eligibilityModule.minimumAge",
        db_path=db_path,
        nct_id="NCT99999999",
    )
    assert missing["results"][0]["found"] is False


def test_get_protocol_field_rejects_unsafe_paths(tmp_path) -> None:
    db_path = tmp_path / "protocols.db"
    save_documents(
        db_path,
        [
            ProtocolDocument(
                nct_id="NCT00000001",
                brief_title="Toy",
                document={"protocolSection": {}},
            )
        ],
    )
    try:
        get_protocol_field("protocolSection; DROP TABLE protocol_documents", db_path=db_path)
    except ValueError as exc:
        assert "JSON path" in str(exc)
    else:
        raise AssertionError("expected invalid path to raise")
