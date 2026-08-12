"""Protocol RAG helpers: parse cached CT.gov JSON and chunk labeled sections."""

from pathlib import Path

from app.rag.chunk import Chunk, chunk_section, chunk_sections
from app.rag.parse import ProtocolSection, iter_protocol_files, parse_study, parse_study_file
from app.rag.store import load_chunks_from_path, save_chunks


def ingest_protocol_dir(protocols_dir: Path | str) -> list[Chunk]:
    """Parse and chunk every cached study JSON under ``protocols_dir``."""
    chunks: list[Chunk] = []
    for path in iter_protocol_files(protocols_dir):
        chunks.extend(chunk_sections(parse_study_file(path)))
    return chunks


def persist_protocol_dir(
    protocols_dir: Path | str,
    db_path: Path | str,
) -> list[Chunk]:
    """Parse, chunk, and replace SQLite content rows at ``db_path``."""
    return save_chunks(db_path, ingest_protocol_dir(protocols_dir))


__all__ = [
    "Chunk",
    "ProtocolSection",
    "chunk_section",
    "chunk_sections",
    "ingest_protocol_dir",
    "iter_protocol_files",
    "load_chunks_from_path",
    "parse_study",
    "parse_study_file",
    "persist_protocol_dir",
    "save_chunks",
]
