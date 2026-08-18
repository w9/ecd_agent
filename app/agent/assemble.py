"""Ground the model's answer; do not write canned prose."""

from __future__ import annotations

import re

from app.agent.tools import EvidenceLedger
from app.grounding import format_number, grounded_citations
from app.schemas import Citation, QueryResponse, Route, Source

_SITE_ID_TOKEN = re.compile(r"SITE-\d+", re.I)
_SITE_BINDING_PHRASE = re.compile(
    r"\s+(?:associated with|found for|at|for)\s+SITE-\d+\b",
    re.I,
)
_LOOSE_SITE_BINDING = re.compile(r"\b(?:associated with|found for)\b", re.I)
_NUMBER_CORE = re.compile(r"^-?\d+(?:\.\d+)?$")
_EMBEDDED_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])")
_TOKEN_PUNCT = ".,;:()[]"


def assemble(query: str, ledger: EvidenceLedger, model_answer: str | None) -> QueryResponse:
    del query
    route = _infer_route(ledger)
    answer = (model_answer or "").strip()

    if route == "reject":
        return QueryResponse(
            answer=_drop_ungrounded_tokens(answer, allowed_ids=set(), allowed_numbers=set()),
            route="reject",
            source="none",
            citations=[],
        )

    if route == "protocol" and _unscoped_multi_study(ledger):
        answer = _unbind_sites_from_protocol_answer(answer)
        answer = _drop_ungrounded_tokens(answer, allowed_ids=set(), allowed_numbers=set())
        return QueryResponse(
            answer=answer,
            route="protocol",
            source="none",
            citations=[],
        )

    if route == "protocol":
        answer = _unbind_sites_from_protocol_answer(answer)
        answer = _drop_ungrounded_tokens(
            answer,
            allowed_ids=set(),
            allowed_numbers=_chunk_numbers(ledger),
        )
    elif route == "hybrid":
        answer = _drop_ungrounded_tokens(
            answer,
            allowed_ids=set(_allowed_site_ids(ledger)),
            allowed_numbers=_site_numbers(ledger) | _chunk_numbers(ledger),
        )
    else:
        answer = _pin_site_evidence(answer, ledger)

    citations = _citations(ledger, answer)
    source = _infer_source(ledger, route)
    return QueryResponse(answer=answer, route=route, source=source, citations=citations)


def _infer_route(ledger: EvidenceLedger) -> Route:
    if ledger.used_site_tool and ledger.used_protocol_tool:
        return "hybrid"
    if ledger.used_protocol_tool:
        return "protocol"
    if ledger.used_site_tool:
        return "site"
    return "reject"


def _infer_source(ledger: EvidenceLedger, route: Route) -> Source:
    has_protocol = bool(ledger.protocol_chunks)
    has_sites = bool(ledger.site_rows) or any(
        item.get("found") and item.get("field") for item in ledger.metric_results
    )
    if route == "hybrid":
        if has_protocol and has_sites:
            return "hybrid"
        if has_protocol:
            return "protocol"
        if has_sites:
            return "sites"
        return "none"
    if route == "protocol":
        return "protocol" if has_protocol else "none"
    if route == "site":
        return "sites" if has_sites or ledger.site_rows else "none"
    return "none"


def _unscoped_multi_study(ledger: EvidenceLedger) -> bool:
    if ledger.protocol_scoped_to_nct:
        return False
    ncts = {
        str(chunk.get("nct_id")).upper()
        for chunk in ledger.protocol_chunks
        if chunk.get("nct_id")
    }
    return len(ncts) > 1


def _unbind_sites_from_protocol_answer(answer: str) -> str:
    """Drop site IDs from protocol-only answers; chunks are not site-bound."""
    cleaned = _SITE_BINDING_PHRASE.sub("", answer)
    cleaned = _SITE_ID_TOKEN.sub("", cleaned)
    cleaned = _LOOSE_SITE_BINDING.sub("", cleaned)
    return re.sub(r" {2,}", " ", cleaned).strip()


def _citations(ledger: EvidenceLedger, answer: str) -> list[Citation]:
    citations: list[Citation] = []
    seen_protocol: set[tuple[str, str]] = set()
    for chunk in ledger.protocol_chunks:
        nct_id = chunk.get("nct_id")
        section = chunk.get("section")
        if not nct_id or not section:
            continue
        key = (str(nct_id), str(section))
        if key in seen_protocol:
            continue
        seen_protocol.add(key)
        citations.append(
            Citation(source="protocol", nct_id=str(nct_id), section=str(section))
        )
    citations = grounded_citations(citations, ledger.protocol_chunks)

    allowed_sites = _allowed_site_ids(ledger)
    mentioned = [
        allowed_sites[match.group(0).upper()]
        for match in _SITE_ID_TOKEN.finditer(answer)
        if match.group(0).upper() in allowed_sites
    ]
    site_ids = mentioned or list(allowed_sites.values())
    seen_sites: set[str] = set()
    for site_id in site_ids:
        if site_id in seen_sites:
            continue
        seen_sites.add(site_id)
        citations.append(Citation(source="sites", site_id=site_id))
    return citations


def _allowed_site_ids(ledger: EvidenceLedger) -> dict[str, str]:
    allowed: dict[str, str] = {}
    for row in ledger.site_rows:
        site_id = row.get("site_id")
        if isinstance(site_id, str) and site_id:
            allowed[site_id.upper()] = site_id
    for item in ledger.metric_results:
        site_id = item.get("site_id")
        if item.get("found") and isinstance(site_id, str) and site_id:
            allowed[site_id.upper()] = site_id
    return allowed


def _pin_site_evidence(answer: str, ledger: EvidenceLedger) -> str:
    """Drop invented site IDs; keep tool numbers as the source of truth."""
    allowed_ids = set(_allowed_site_ids(ledger))
    allowed_numbers = _site_numbers(ledger)
    replacement = None
    if len(allowed_numbers) == 1:
        value = next(iter(allowed_numbers))
        replacement = format_number(value)
    return _drop_ungrounded_tokens(
        answer,
        allowed_ids=allowed_ids,
        allowed_numbers=allowed_numbers,
        replacement=replacement,
    )


def _drop_ungrounded_tokens(
    answer: str,
    *,
    allowed_ids: set[str],
    allowed_numbers: set[float],
    replacement: str | None = None,
) -> str:
    kept: list[str] = []
    for token in answer.split():
        prefix, core, suffix = _split_punct(token)
        if core.upper().startswith("SITE-"):
            if core.upper() not in {site_id.upper() for site_id in allowed_ids}:
                continue
            kept.append(token)
            continue
        if _NUMBER_CORE.match(core):
            value = float(core)
            if any(value == allowed for allowed in allowed_numbers):
                kept.append(token)
                continue
            if replacement is not None:
                kept.append(f"{prefix}{replacement}{suffix}")
            continue
        kept.append(token)
    return " ".join(kept)


def _split_punct(token: str) -> tuple[str, str, str]:
    start = 0
    end = len(token)
    while start < end and token[start] in _TOKEN_PUNCT:
        start += 1
    while end > start and token[end - 1] in _TOKEN_PUNCT:
        end -= 1
    return token[:start], token[start:end], token[end:]


def _site_numbers(ledger: EvidenceLedger) -> set[float]:
    values: set[float] = set()
    for row in ledger.site_rows:
        for key in ("monthly_enrollment_rate", "active_trials", "remaining_slots"):
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.add(float(value))
    for item in ledger.metric_results:
        value = item.get("value")
        if (
            item.get("found")
            and item.get("field")
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            values.add(float(value))
    return values


def _chunk_numbers(ledger: EvidenceLedger) -> set[float]:
    values: set[float] = set()
    for chunk in ledger.protocol_chunks:
        text = chunk.get("text")
        if not isinstance(text, str):
            continue
        for match in _EMBEDDED_NUMBER.finditer(text):
            values.add(float(match.group(0)))
    return values
