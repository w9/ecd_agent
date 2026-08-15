"""Assemble a grounded QueryResponse from routing, tools, retrieval, and the LLM."""

from __future__ import annotations

import re
from pathlib import Path

import app.llm as llm
from app.grounding import format_number, grounded_citations, must_abstain
from app.llm import LLMError
from app.rag.chunk import Chunk
from app.rag.store import load_chunks_from_path, search_chunks_from_path
from app.routing import (
    classify,
    extract_metric_field,
    extract_nct_id,
    extract_site_id,
    extract_therapeutic_area,
    is_ranking_query,
)
from app.schemas import Citation, QueryRequest, QueryResponse
from app.tools.sites import list_sites, lookup_site, rank_sites

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

_PROTOCOL_SYSTEM = (
    "Answer only from the retrieved protocol excerpts. "
    "If they do not contain the answer, say you do not have that information. "
    "Do not invent site enrollment numbers or cite studies that were not retrieved."
)
_HYBRID_SYSTEM = (
    "Recommend sites using both the protocol excerpts and the site table rows. "
    "Do not invent sites, NCT IDs, or numeric metrics. "
    "Keep every number exactly as given in the site rows."
)


def handle_query(
    request: QueryRequest,
    *,
    sites_db_path: Path | str,
    protocols_db_path: Path | str,
) -> QueryResponse:
    query = request.query
    nct_id = request.nct_id or extract_nct_id(query)
    site_id = extract_site_id(query)
    decision = classify(query)

    if decision.route == "reject":
        return _reject(query, decision.reason)

    if decision.route == "site":
        if is_ranking_query(query):
            return _site_ranking(query, sites_db_path)
        if not site_id:
            return _reject(query, "need_site")
        return _site_lookup(query, site_id, sites_db_path)

    if decision.route == "protocol":
        if not nct_id and not site_id:
            return _reject(query, "need_nct")
        return _protocol_answer(query, nct_id, protocols_db_path)

    if not nct_id:
        return _reject(query, "need_nct")
    return _hybrid_answer(query, nct_id, sites_db_path, protocols_db_path)


def _site_lookup(query: str, site_id: str, db_path: Path | str) -> QueryResponse:
    row = lookup_site(site_id, db_path=db_path)
    if row is None:
        return QueryResponse(
            answer=f"I don't have any information on site {site_id}.",
            route="site",
            source="none",
            citations=[],
        )

    field = extract_metric_field(query)
    citations = [Citation(source="sites", site_id=row["site_id"])]
    if field is None:
        return QueryResponse(
            answer=_format_site_row(row),
            route="site",
            source="sites",
            citations=citations,
        )

    value = row.get(field)
    if value is None:
        label = field.replace("_", " ")
        return QueryResponse(
            answer=f"The {label} for {row['site_id']} is not available.",
            route="site",
            source="sites",
            citations=citations,
        )
    return QueryResponse(
        answer=_format_metric_answer(row["site_id"], field, value),
        route="site",
        source="sites",
        citations=citations,
    )


def _site_ranking(query: str, db_path: Path | str) -> QueryResponse:
    area = extract_therapeutic_area(query)
    ranked = rank_sites(
        db_path=db_path,
        field="monthly_enrollment_rate",
        therapeutic_area=area,
        limit=1,
    )
    if not ranked:
        return QueryResponse(
            answer="I don't have any information to rank sites for that query.",
            route="site",
            source="none",
            citations=[],
        )
    top = ranked[0]
    rate = format_number(top["monthly_enrollment_rate"])
    area_text = f" among {area.lower()} sites" if area else ""
    return QueryResponse(
        answer=(
            f"{top['site_id']} has the highest enrollment rate{area_text} at {rate}."
        ),
        route="site",
        source="sites",
        citations=[Citation(source="sites", site_id=top["site_id"])],
    )


def _protocol_answer(
    query: str,
    nct_id: str | None,
    db_path: Path | str,
) -> QueryResponse:
    hits = _retrieve_chunks(query, nct_id, db_path)
    if must_abstain(hits, None):
        return QueryResponse(
            answer="I don't have any information in the ingested protocols for that question.",
            route="protocol",
            source="none",
            citations=[],
        )
    answer = _generate(query, hits=hits, sites=None, system=_PROTOCOL_SYSTEM)
    citations = grounded_citations(_protocol_citations(hits), hits)
    return QueryResponse(
        answer=answer,
        route="protocol",
        source="protocol",
        citations=citations,
    )


def _hybrid_answer(
    query: str,
    nct_id: str,
    sites_db_path: Path | str,
    protocols_db_path: Path | str,
) -> QueryResponse:
    hits = _retrieve_chunks(query, nct_id, protocols_db_path)
    area = extract_therapeutic_area(query)
    sites = rank_sites(
        db_path=sites_db_path,
        field="monthly_enrollment_rate",
        therapeutic_area=area,
        limit=4,
    )
    if not sites:
        sites = list_sites(db_path=sites_db_path, therapeutic_area=area)
    if must_abstain(hits, sites or None):
        return QueryResponse(
            answer="I don't have enough protocol and site evidence to make a recommendation.",
            route="hybrid",
            source="none",
            citations=[],
        )
    answer = _generate(query, hits=hits, sites=sites, system=_HYBRID_SYSTEM)
    citations = grounded_citations(_protocol_citations(hits), hits)
    citations.extend(
        Citation(source="sites", site_id=row["site_id"])
        for row in sites
        if row.get("site_id")
    )
    source = "hybrid" if hits and sites else ("protocol" if hits else "sites")
    return QueryResponse(
        answer=answer,
        route="hybrid",
        source=source,
        citations=citations,
    )


def _generate(
    query: str,
    *,
    hits: list[Chunk],
    sites: list[dict] | None,
    system: str,
) -> str:
    prompt_parts = [f"User question: {query}"]
    if hits:
        excerpts = "\n\n".join(
            f"[{chunk.nct_id} | {chunk.section}]\n{chunk.text}" for chunk in hits
        )
        prompt_parts.append(f"Retrieved protocol excerpts:\n{excerpts}")
    if sites:
        rows = "\n".join(_format_site_row(row) for row in sites)
        prompt_parts.append(f"Site table rows:\n{rows}")
    prompt_parts.append("Answer using only the evidence above.")
    try:
        return llm.complete("\n\n".join(prompt_parts), system=system)
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError("LLM unavailable") from exc


def _retrieve_chunks(query: str, nct_id: str | None, db_path: Path | str) -> list[Chunk]:
    path = Path(db_path)
    if not path.is_file():
        return []
    if nct_id:
        try:
            return [chunk for chunk in load_chunks_from_path(path) if chunk.nct_id.upper() == nct_id]
        except Exception:
            return []
    fts = _fts_query(query)
    if not fts:
        return []
    try:
        return [chunk for chunk, _rank in search_chunks_from_path(path, fts, limit=8)]
    except Exception:
        return []


def _fts_query(query: str) -> str:
    tokens = [token for token in _FTS_TOKEN.findall(query) if token.lower() not in _FTS_STOP]
    return " OR ".join(tokens)


def _protocol_citations(hits: list[Chunk]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    citations: list[Citation] = []
    for chunk in hits:
        key = (chunk.nct_id, chunk.section)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(source="protocol", nct_id=chunk.nct_id, section=chunk.section)
        )
    return citations


def _format_metric_answer(site_id: str, field: str, value: float | int) -> str:
    number = format_number(value)
    if field == "monthly_enrollment_rate":
        return f"The monthly enrollment rate for {site_id} is {number}."
    if field == "active_trials":
        return f"There are {number} active trials at {site_id}."
    if field == "remaining_slots":
        return f"{site_id} has {number} remaining slots."
    return f"The {field.replace('_', ' ')} for {site_id} is {number}."


def _format_site_row(row: dict) -> str:
    site_id = row.get("site_id", "unknown")
    parts = [f"{site_id} ({row.get('site_name') or 'unnamed site'})"]
    if row.get("therapeutic_area"):
        parts.append(f"therapeutic area {row['therapeutic_area']}")
    rate = row.get("monthly_enrollment_rate")
    if rate is not None:
        parts.append(f"monthly enrollment rate {format_number(rate)}")
    trials = row.get("active_trials")
    if trials is not None:
        parts.append(f"{format_number(trials)} active trials")
    slots = row.get("remaining_slots")
    if slots is not None:
        parts.append(f"{format_number(slots)} remaining slots")
    return "; ".join(parts) + "."


def _reject(query: str, reason: str) -> QueryResponse:
    if reason == "need_site":
        answer = "Please provide a site_id so I can look up that enrollment metric."
    elif reason == "need_nct":
        answer = "Please provide an NCT ID for the study you want me to look up."
    elif reason == "unsafe":
        lowered = query.lower()
        if "patient" in lowered or "chart" in lowered or "john doe" in lowered:
            answer = (
                "I can't process patient charts or give medical advice. "
                "Ask about a site_id or an NCT ID without personal health information."
            )
        elif "protocol" in lowered:
            answer = (
                "I can't write a new clinical protocol from scratch. "
                "I can only answer questions about ingested public protocols and mock site data."
            )
        else:
            answer = "I can't help with that request."
    else:
        answer = "I need a more specific question about a site_id or an NCT ID / study."
    return QueryResponse(answer=answer, route="reject", source="none", citations=[])
