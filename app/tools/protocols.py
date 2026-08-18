"""Read-only protocol chunk retrieval for the agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.rag.chunk import Chunk
from app.rag.store import (
    extract_json_field,
    load_chunks_for_nct,
    search_chunks_from_path,
)

_JSON_PATH = re.compile(
    r"^\$"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"|\[\d+\])*$"
)
MAX_FIELD_CHARS = 24_000

DEFAULT_CHUNK_LIMIT = 8
SCOPED_FTS_FETCH = 24

_FTS_TOKEN = re.compile(r"[A-Za-z]{3,}")
_SITE_ID = re.compile(r"\bSITE-\d+\b", re.I)
_ELIGIBILITY_QUERY = re.compile(
    r"(enrollment|inclusion|exclusion)\s+criteria|\beligibility\b",
    re.I,
)
_OUTCOME_QUERY = re.compile(r"\b(outcomes?|endpoints?)\b", re.I)
_ELIGIBILITY_FTS = "eligibility OR inclusion OR exclusion"
_FEASIBILITY_SECTIONS = frozenset(
    {
        "conditions",
        "design",
        "interventions",
        "interventions.arms",
        "eligibility.structured",
        "eligibility.inclusion",
        "eligibility.exclusion",
        "eligibility.criteria",
    }
)
_SUMMARY_FIELDS = (
    ("brief_title", "$.protocolSection.identificationModule.briefTitle"),
    ("conditions", "$.protocolSection.conditionsModule.conditions"),
    ("keywords", "$.protocolSection.conditionsModule.keywords"),
    ("phases", "$.protocolSection.designModule.phases"),
    ("study_type", "$.protocolSection.designModule.studyType"),
    ("primary_purpose", "$.protocolSection.designModule.designInfo.primaryPurpose"),
    ("enrollment", "$.protocolSection.designModule.enrollmentInfo"),
    ("minimum_age", "$.protocolSection.eligibilityModule.minimumAge"),
    ("maximum_age", "$.protocolSection.eligibilityModule.maximumAge"),
    ("sex", "$.protocolSection.eligibilityModule.sex"),
    ("healthy_volunteers", "$.protocolSection.eligibilityModule.healthyVolunteers"),
)
SUMMARY_CITE_SECTIONS = frozenset(
    {"summary", "conditions", "design", "eligibility.structured"}
)
COMMON_PROTOCOL_PATHS = tuple(path for _name, path in _SUMMARY_FIELDS)
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
    limit: int = DEFAULT_CHUNK_LIMIT,
) -> list[dict[str, Any]]:
    """Return protocol chunks for an NCT ID or an FTS query.

    Scoped searches stay inside that NCT, cap the result, and drop outcome
    sections unless the query is about endpoints.
    """
    chunks = _retrieve_chunks(query, nct_id, db_path, limit=limit)
    return [_chunk_payload(chunk) for chunk in chunks]


def get_study_summary(
    *,
    db_path: Path | str,
    nct_id: str | None = None,
) -> dict[str, Any]:
    """Return a compact card of common CT.gov fields for one or every study."""
    by_nct: dict[str, dict[str, Any]] = {}
    for name, path in _SUMMARY_FIELDS:
        for row in extract_json_field(db_path, path, nct_id=nct_id):
            study_id = str(row.get("nct_id") or "").strip().upper()
            if not study_id:
                continue
            study = by_nct.setdefault(study_id, {"nct_id": study_id})
            study[name] = row["value"] if row.get("found") else None
    studies = list(by_nct.values())
    if nct_id and not studies:
        studies = [
            {
                "nct_id": nct_id.strip().upper(),
                **{name: None for name, _path in _SUMMARY_FIELDS},
            }
        ]
    return {
        "nct_id": nct_id,
        "scoped_to_nct": bool(nct_id),
        "studies": studies,
        "site_bound": False,
        "paths": {name: path for name, path in _SUMMARY_FIELDS},
        "note": (
            "Compact fields from the raw CT.gov document. "
            "Prefer this over search_protocol for site recommendations. "
            "Use get_protocol_field only for a path that is not listed here."
        ),
    }


def get_protocol_field(
    path: str,
    *,
    db_path: Path | str,
    nct_id: str | None = None,
) -> dict[str, Any]:
    """Extract one JSON path from stored CT.gov documents.

    ``nct_id`` is optional: omit it to return the field for every ingested study.
    """
    normalized = normalize_json_path(path)
    results = extract_json_field(db_path, normalized, nct_id=nct_id)
    if nct_id and not results:
        results = [
            {
                "nct_id": nct_id,
                "path": normalized,
                "found": False,
                "value": None,
                "json_type": None,
            }
        ]
    capped: list[dict[str, Any]] = []
    for row in results:
        capped.append(_cap_field_value(row))
    return {
        "path": normalized,
        "nct_id": nct_id,
        "scoped_to_nct": bool(nct_id),
        "results": capped,
        "site_bound": False,
        "note": (
            "Values come from json_extract on the raw CT.gov document. "
            "Use a dotted path such as "
            "$.protocolSection.eligibilityModule.minimumAge. "
            "If scoped_to_nct is false, results include every ingested study."
        ),
    }


def normalize_json_path(path: str) -> str:
    """Accept ``$.a.b`` or ``a.b`` and return a SQLite json_extract path."""
    stripped = path.strip()
    if not stripped:
        raise ValueError("path must be a non-empty JSON path")
    if not stripped.startswith("$"):
        stripped = f"$.{stripped.lstrip('.')}"
    if not _JSON_PATH.fullmatch(stripped):
        raise ValueError(
            "path must be a JSON path like $.protocolSection.eligibilityModule.minimumAge"
        )
    return stripped


def _cap_field_value(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("value")
    if value is None:
        return row
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    if len(encoded) <= MAX_FIELD_CHARS:
        return row
    capped = dict(row)
    capped["value"] = None
    capped["truncated"] = True
    capped["error"] = (
        f"value is {len(encoded)} characters; use a more specific path"
    )
    return capped


def is_eligibility_query(query: str) -> bool:
    """True for inclusion/exclusion/enrollment-criteria lookalikes."""
    return bool(_ELIGIBILITY_QUERY.search(query))


def is_outcome_query(query: str) -> bool:
    """True when the question is about endpoints or outcome measures."""
    return bool(_OUTCOME_QUERY.search(query))


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
        return _retrieve_scoped(query, nct_id, path, limit=limit)
    fts = _fts_query(query)
    if not fts:
        return []
    try:
        chunks = [
            chunk
            for chunk, _rank in search_chunks_from_path(path, fts, limit=limit)
        ]
    except Exception:
        return []
    if is_eligibility_query(query):
        return [chunk for chunk in chunks if _is_eligibility_section(chunk.section)]
    return chunks


def _retrieve_scoped(
    query: str,
    nct_id: str,
    db_path: Path,
    *,
    limit: int,
) -> list[Chunk]:
    fts_chunks: list[Chunk] = []
    fts = _fts_query(query)
    if fts:
        try:
            fts_chunks = [
                chunk
                for chunk, _rank in search_chunks_from_path(
                    db_path,
                    fts,
                    limit=max(limit, SCOPED_FTS_FETCH),
                    nct_id=nct_id,
                )
            ]
        except Exception:
            fts_chunks = []
    selected = _select_chunks(fts_chunks, query, limit=limit) if fts_chunks else []
    if selected and not _needs_feasibility_fallback(selected, query):
        return selected
    try:
        loaded = load_chunks_for_nct(db_path, nct_id)
    except Exception:
        return selected
    fallback = _select_chunks(loaded, query, limit=limit)
    return fallback or selected


def _needs_feasibility_fallback(chunks: list[Chunk], query: str) -> bool:
    if is_outcome_query(query) or is_eligibility_query(query):
        return False
    return _only_outcome_sections(chunks)


def _select_chunks(chunks: list[Chunk], query: str, *, limit: int) -> list[Chunk]:
    if is_eligibility_query(query):
        return [
            chunk for chunk in chunks if _is_eligibility_section(chunk.section)
        ][:limit]
    if is_outcome_query(query):
        return chunks[:limit]
    preferred = [
        chunk for chunk in chunks if _is_feasibility_section(chunk.section)
    ]
    if preferred:
        return _one_chunk_per_section(preferred)[:limit]
    without_outcomes = [
        chunk
        for chunk in chunks
        if not str(chunk.section).lower().startswith("outcomes.")
    ]
    return (without_outcomes or chunks)[:limit]


def _one_chunk_per_section(chunks: list[Chunk]) -> list[Chunk]:
    seen: set[tuple[str, str]] = set()
    unique: list[Chunk] = []
    for chunk in chunks:
        key = (chunk.nct_id.upper(), chunk.section)
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def _only_outcome_sections(chunks: list[Chunk]) -> bool:
    return bool(chunks) and all(
        str(chunk.section).lower().startswith("outcomes.") for chunk in chunks
    )


def _is_feasibility_section(section: str) -> bool:
    lowered = str(section).lower()
    return lowered in _FEASIBILITY_SECTIONS or lowered.startswith("eligibility.")


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
