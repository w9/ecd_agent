"""Read-only protocol chunk retrieval for the agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.rag.chunk import Chunk
from app.rag.store import load_chunks_from_path, search_chunks_from_path

_FTS_TOKEN = re.compile(r"[A-Za-z]{3,}")
_FTS_STOP = {
    "about",
    "and",
    "are",
    "does",
    "for",
    "from",
    "given",
    "have",
    "how",
    "many",
    "next",
    "should",
    "site",
    "tell",
    "that",
    "the",
    "this",
    "what",
    "where",
    "which",
    "with",
}


def search_protocol(
    query: str,
    *,
    db_path: Path | str,
    nct_id: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return protocol chunks for an NCT ID or an FTS query."""
    chunks = _retrieve_chunks(query, nct_id, db_path, limit=limit)
    return [_chunk_payload(chunk) for chunk in chunks]


def _retrieve_chunks(
    query: str,
    nct_id: str | None,
    db_path: Path | str,
    *,
    limit: int,
) -> list[Chunk]:
    path = Path(db_path)
    if not path.is_file():
        return []
    if nct_id:
        try:
            return [
                chunk
                for chunk in load_chunks_from_path(path)
                if chunk.nct_id.upper() == nct_id.upper()
            ]
        except Exception:
            return []
    fts = _fts_query(query)
    if not fts:
        return []
    try:
        return [chunk for chunk, _rank in search_chunks_from_path(path, fts, limit=limit)]
    except Exception:
        return []


def _fts_query(query: str) -> str:
    tokens = [token for token in _FTS_TOKEN.findall(query) if token.lower() not in _FTS_STOP]
    return " OR ".join(tokens)


def _chunk_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "nct_id": chunk.nct_id,
        "section": chunk.section,
        "text": chunk.text,
        "brief_title": chunk.brief_title,
    }
