"""Tests for ClinicalTrials.gov JSON flattening."""

from app.rag.parse import CachedProtocol, list_cached_protocols, parse_study

SAMPLE_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT00000001",
            "briefTitle": "Toy vaccine study",
        },
        "conditionsModule": {
            "conditions": ["COVID-19", "SARS-CoV-2"],
            "keywords": ["vaccine"],
        },
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE3"],
            "designInfo": {
                "allocation": "RANDOMIZED",
                "interventionModel": "PARALLEL",
                "primaryPurpose": "PREVENTION",
                "maskingInfo": {
                    "masking": "QUADRUPLE",
                    "whoMasked": ["PARTICIPANT", "INVESTIGATOR"],
                },
            },
            "enrollmentInfo": {"count": 100, "type": "ACTUAL"},
        },
        "armsInterventionsModule": {
            "armGroups": [
                {
                    "label": "Vaccine",
                    "type": "EXPERIMENTAL",
                    "description": "Two doses of AZD1222",
                    "interventionNames": ["Biological: AZD1222"],
                }
            ],
            "interventions": [
                {
                    "type": "BIOLOGICAL",
                    "name": "AZD1222",
                    "description": "ChAdOx1 vector vaccine",
                    "armGroupLabels": ["Vaccine"],
                    "otherNames": ["Vaxzevria"],
                }
            ],
        },
        "outcomesModule": {
            "primaryOutcomes": [
                {
                    "measure": "COVID-19 cases",
                    "description": "RT-PCR-positive symptomatic illness",
                    "timeFrame": "15 days post second dose",
                }
            ],
            "secondaryOutcomes": [
                {
                    "measure": "Antibody response",
                    "timeFrame": "28 days",
                }
            ],
        },
        "eligibilityModule": {
            "eligibilityCriteria": (
                "Inclusion Criteria:\n\n"
                "* Age 18 years or older\n"
                "* Medically stable\n\n"
                "Exclusion Criteria:\n\n"
                "* Prior COVID-19 vaccine\n"
                "* Immunodeficiency"
            ),
            "healthyVolunteers": True,
            "sex": "ALL",
            "minimumAge": "18 Years",
            "maximumAge": "130 Years",
            "stdAges": ["ADULT", "OLDER_ADULT"],
        },
    },
    "resultsSection": {
        "adverseEventsModule": {"note": "should not be indexed"},
    },
}


def _by_section(sections) -> dict[str, str]:
    return {item.section: item.text for item in sections}


def test_parse_study_extracts_labeled_sections() -> None:
    sections = parse_study(SAMPLE_STUDY)
    by_section = _by_section(sections)

    assert {item.nct_id for item in sections} == {"NCT00000001"}
    assert {item.brief_title for item in sections} == {"Toy vaccine study"}
    assert "conditions" in by_section
    assert "COVID-19" in by_section["conditions"]
    assert "PHASE3" in by_section["design"]
    assert "Enrollment: 100 (ACTUAL)" in by_section["design"]
    assert "AZD1222" in by_section["interventions"]
    assert "Vaxzevria" in by_section["interventions"]
    assert "Two doses of AZD1222" in by_section["interventions.arms"]
    assert "COVID-19 cases" in by_section["outcomes.primary"]
    assert "Antibody response" in by_section["outcomes.secondary"]
    assert "Minimum age: 18 Years" in by_section["eligibility.structured"]
    assert "Healthy volunteers: yes" in by_section["eligibility.structured"]
    assert "Age 18 years or older" in by_section["eligibility.inclusion"]
    assert "Prior COVID-19 vaccine" in by_section["eligibility.exclusion"]
    assert "eligibility.criteria" not in by_section
    assert all("should not be indexed" not in item.text for item in sections)


def test_parse_study_keeps_unsectioned_eligibility() -> None:
    payload = {
        "protocolSection": {
            "identificationModule": {"nctId": "nct00000002", "briefTitle": "Bare"},
            "eligibilityModule": {"eligibilityCriteria": "Must be able to consent."},
        }
    }
    sections = parse_study(payload)
    assert len(sections) == 1
    assert sections[0].nct_id == "NCT00000002"
    assert sections[0].section == "eligibility.criteria"
    assert sections[0].text == "Must be able to consent."


def test_parse_study_skips_empty_modules() -> None:
    payload = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000003", "briefTitle": "Empty"},
            "conditionsModule": {"conditions": []},
            "outcomesModule": {},
        }
    }
    assert parse_study(payload) == []


def test_list_cached_protocols_reads_identity_and_skips_junk(tmp_path) -> None:
    good = tmp_path / "NCT00000001.json"
    good.write_text(
        '{"protocolSection":{"identificationModule":'
        '{"nctId":"NCT00000001","briefTitle":"Toy vaccine study"}}}',
        encoding="utf-8",
    )
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / "NCT04516746.json").write_text("[]", encoding="utf-8")

    assert list_cached_protocols(tmp_path) == [
        CachedProtocol(nct_id="NCT00000001", brief_title="Toy vaccine study"),
        CachedProtocol(nct_id="NCT04516746", brief_title=""),
    ]
    assert list_cached_protocols(tmp_path / "missing") == []
