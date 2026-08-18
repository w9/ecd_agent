"""Protocol RAG helpers: parse cached CT.gov JSON and chunk labeled sections."""

from pathlib import Path

from app.rag.chunk import Chunk, chunk_section, chunk_sections
from app.rag.parse import (
    ProtocolSection,
    iter_protocol_files,
    load_study_payload,
    parse_study,
    parse_study_file,
    study_identity,
)
from app.rag.store import (
    ProtocolDocument,
    load_chunks_from_path,
    save_chunks,
    save_documents,
    search_chunks_from_path,
)


def ingest_protocol_dir(protocols_dir: Path | str) -> list[Chunk]:
    """Parse and chunk every cached study JSON under ``protocols_dir``."""
    chunks: list[Chunk] = []
    for path in iter_protocol_files(protocols_dir):
        chunks.extend(chunk_sections(parse_study_file(path)))
    return chunks


def ingest_protocol_documents(protocols_dir: Path | str) -> list[ProtocolDocument]:
    """Load raw cached CT.gov JSON documents for SQLite JSON storage."""
    documents: list[ProtocolDocument] = []
    for path in iter_protocol_files(protocols_dir):
        payload = load_study_payload(path)
        nct_id, brief_title = study_identity(payload, fallback_nct=path.stem)
        if not nct_id:
            raise ValueError(f"Study JSON is missing nctId: {path}")
        documents.append(
            ProtocolDocument(nct_id=nct_id, brief_title=brief_title, document=payload)
        )
    return documents


def persist_protocol_dir(
    protocols_dir: Path | str,
    db_path: Path | str,
) -> list[Chunk]:
    """Parse, chunk, store raw JSON documents, and replace SQLite rows."""
    chunks = save_chunks(db_path, ingest_protocol_dir(protocols_dir))
    save_documents(db_path, ingest_protocol_documents(protocols_dir))
    return chunks


__all__ = [
    "Chunk",
    "ProtocolDocument",
    "ProtocolSection",
    "chunk_section",
    "chunk_sections",
    "ingest_protocol_dir",
    "ingest_protocol_documents",
    "iter_protocol_files",
    "load_chunks_from_path",
    "parse_study",
    "parse_study_file",
    "persist_protocol_dir",
    "save_chunks",
    "save_documents",
    "search_chunks_from_path",
]
