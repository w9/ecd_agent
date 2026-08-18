"""Tests for unscoped protocol search rewriting and eligibility filtering."""

from pathlib import Path

from app.rag.chunk import Chunk
from app.rag.store import ProtocolDocument, save_chunks, save_documents
from app.tools.protocols import (
    get_protocol_field,
    get_study_summary,
    is_eligibility_query,
    is_outcome_query,
    search_protocol,
)


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


def test_scoped_search_caps_chunks_and_drops_outcomes(tmp_path: Path) -> None:
    db_path = tmp_path / "protocols.db"
    chunks = [
        _chunk(
            nct_id="NCT04368728",
            section="conditions",
            text="Conditions: SARS-CoV-2 Infection, COVID-19",
            end_char=42,
        ),
        _chunk(
            nct_id="NCT04368728",
            section="design",
            text="Study type: INTERVENTIONAL. Phases: PHASE2, PHASE3.",
            end_char=50,
            chunk_index=1,
        ),
        _chunk(
            nct_id="NCT04368728",
            section="eligibility.structured",
            text="Minimum age: 12 Years. Sex: ALL.",
            end_char=32,
            chunk_index=2,
        ),
    ]
    chunks.extend(
        _chunk(
            nct_id="NCT04368728",
            section="outcomes.primary",
            text=f"Primary outcome {index}: local reactions after dose {index}.",
            end_char=48,
            chunk_index=index + 3,
        )
        for index in range(20)
    )
    save_chunks(db_path, chunks)

    found = search_protocol(
        "condition intervention study phase enrollment eligibility",
        db_path=db_path,
        nct_id="NCT04368728",
    )
    assert len(found) <= 8
    assert {chunk["section"] for chunk in found} <= {
        "conditions",
        "design",
        "eligibility.structured",
    }
    assert not any(chunk["section"].startswith("outcomes.") for chunk in found)


def test_scoped_search_keeps_outcomes_when_asked(tmp_path: Path) -> None:
    db_path = tmp_path / "protocols.db"
    save_chunks(
        db_path,
        [
            _chunk(
                nct_id="NCT04368728",
                section="conditions",
                text="COVID-19",
                end_char=8,
            ),
            _chunk(
                nct_id="NCT04368728",
                section="outcomes.primary",
                text="Primary outcome: COVID-19 incidence after dose 2.",
                end_char=49,
                chunk_index=1,
            ),
        ],
    )
    found = search_protocol(
        "What is the primary outcome?",
        db_path=db_path,
        nct_id="NCT04368728",
    )
    assert any(chunk["section"] == "outcomes.primary" for chunk in found)


def test_get_study_summary_returns_common_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "protocols.db"
    save_documents(
        db_path,
        [
            ProtocolDocument(
                nct_id="NCT04368728",
                brief_title="COVID vaccine",
                document={
                    "protocolSection": {
                        "identificationModule": {
                            "briefTitle": "COVID vaccine",
                        },
                        "conditionsModule": {
                            "conditions": ["COVID-19", "SARS-CoV-2 Infection"],
                            "keywords": ["Vaccine"],
                        },
                        "designModule": {
                            "studyType": "INTERVENTIONAL",
                            "phases": ["PHASE2", "PHASE3"],
                            "designInfo": {"primaryPurpose": "PREVENTION"},
                            "enrollmentInfo": {"count": 46969, "type": "ACTUAL"},
                        },
                        "eligibilityModule": {
                            "minimumAge": "12 Years",
                            "sex": "ALL",
                            "healthyVolunteers": True,
                        },
                    }
                },
            )
        ],
    )

    summary = get_study_summary(db_path=db_path, nct_id="NCT04368728")
    assert summary["scoped_to_nct"] is True
    study = summary["studies"][0]
    assert study["conditions"] == ["COVID-19", "SARS-CoV-2 Infection"]
    assert study["phases"] == ["PHASE2", "PHASE3"]
    assert study["primary_purpose"] == "PREVENTION"
    assert study["enrollment"] == {"count": 46969, "type": "ACTUAL"}
    assert study["minimum_age"] == "12 Years"
    assert study["sex"] == "ALL"
    assert summary["paths"]["conditions"].endswith("conditionsModule.conditions")


def test_is_outcome_query() -> None:
    assert is_outcome_query("What is the primary outcome?")
    assert is_outcome_query("List the endpoints")
    assert not is_outcome_query("Where should I run my next trials?")


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
