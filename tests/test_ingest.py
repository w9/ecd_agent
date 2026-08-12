"""Optional ingest smoke test against cached CT.gov JSON, if present."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.rag import ingest_protocol_dir, parse_study_file

PROTOCOLS_DIR = get_settings().protocols_dir
SAMPLE_PROTOCOL = PROTOCOLS_DIR / "NCT04516746.json"


@pytest.mark.skipif(not SAMPLE_PROTOCOL.is_file(), reason="cached protocol JSON not present")
def test_parse_real_protocol_has_core_sections() -> None:
    sections = parse_study_file(SAMPLE_PROTOCOL)
    names = {item.section for item in sections}
    assert "NCT04516746" == sections[0].nct_id
    assert "conditions" in names
    assert "design" in names
    assert "interventions" in names
    assert "eligibility.structured" in names
    assert any(name.startswith("eligibility.") for name in names)
    assert any(name.startswith("outcomes.") for name in names)


@pytest.mark.skipif(not PROTOCOLS_DIR.is_dir(), reason="protocols directory not present")
def test_ingest_protocol_dir_emits_offsets_inside_section_text() -> None:
    chunks = ingest_protocol_dir(PROTOCOLS_DIR)
    if not chunks:
        pytest.skip("no cached protocol JSON to ingest")
    assert all(chunk.text == chunk.text.strip() for chunk in chunks)
    assert all(0 <= chunk.start_char < chunk.end_char for chunk in chunks)
    assert all(chunk.nct_id.startswith("NCT") for chunk in chunks)
