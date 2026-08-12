"""Tests for protocol section chunking."""

from app.rag.chunk import approx_token_count, chunk_section, chunk_sections
from app.rag.parse import ProtocolSection


def _section(text: str, *, section: str = "eligibility.inclusion") -> ProtocolSection:
    return ProtocolSection(
        nct_id="NCT00000001",
        brief_title="Toy vaccine study",
        section=section,
        text=text,
    )


def test_small_section_is_a_single_chunk() -> None:
    section = _section("Minimum age: 18 Years")
    chunks = chunk_section(section)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.nct_id == "NCT00000001"
    assert chunk.section == "eligibility.inclusion"
    assert chunk.text == "Minimum age: 18 Years"
    assert chunk.start_char == 0
    assert chunk.end_char == len(section.text)
    assert chunk.chunk_index == 0
    assert chunk.labeled_text().startswith("[NCT00000001] Toy vaccine study | eligibility.inclusion")


def test_long_section_uses_overlapping_windows() -> None:
    paragraphs = [
        f"Paragraph {index:02d} " + " ".join(["word"] * 80) for index in range(12)
    ]
    text = "\n\n".join(paragraphs)
    section = _section(text)
    chunks = chunk_section(section, max_tokens=200, overlap_tokens=40)

    assert len(chunks) >= 2
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(text)
    assert all(chunk.text == text[chunk.start_char : chunk.end_char] for chunk in chunks)
    assert all(approx_token_count(chunk.text) <= 200 for chunk in chunks)

    for previous, current in zip(chunks, chunks[1:]):
        assert current.start_char < previous.end_char
        assert current.start_char >= previous.start_char
        overlap = text[current.start_char : previous.end_char]
        assert overlap.strip()


def test_chunk_sections_preserves_order() -> None:
    sections = [
        _section("Conditions: COVID-19", section="conditions"),
        _section("Phases: PHASE3", section="design"),
    ]
    chunks = chunk_sections(sections)
    assert [chunk.section for chunk in chunks] == ["conditions", "design"]
