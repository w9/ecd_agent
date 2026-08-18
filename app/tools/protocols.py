"""Read-only protocol chunk retrieval for the agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.rag.chunk import Chunk
from app.rag.store import load_chunks_from_path, search_chunks_from_path

_FTS_TOKEN = re.compile(r"[A-Za-z]{3,}")
_SITE_ID = re.compile(r"\bSITE-\d+\b", re.I)
_ELIGIBILITY_QUERY = re.compile(
    r"(enrollment|inclusion|exclusion)\s+criteria|\beligibility\b",
    re.I,
)
_ELIGIBILITY_FTS = "eligibility OR inclusion OR exclusion"
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


def is_eligibility_query(query: str) -> bool:
    """True for inclusion/exclusion/enrollment-criteria lookalikes."""
    return bool(_ELIGIBILITY_QUERY.search(query))


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
        chunks = [chunk for chunk, _rank in search_chunks_from_path(path, fts, limit=limit)]
    except Exception:
        return []
    if is_eligibility_query(query):
        return [chunk for chunk in chunks if _is_eligibility_section(chunk.section)]
    return chunks


def _fts_query(query: str) -> str:
    if is_eligibility_query(query):
        return _ELIGIBILITY_FTS
    cleaned = _SITE_ID.sub(" ", query)
    tokens = [token for token in _FTS_TOKEN.findall(cleaned) if token.lower() not in _FTS_STOP]
    return " AND ".join(tokens)


def _is_eligibility_section(section: str) -> bool:
    return str(section).lower().startswith("eligibility.")


def _chunk_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "nct_id": chunk.nct_id,
        "section": chunk.section,
        "text": chunk.text,
        "brief_title": chunk.brief_title,
    }
