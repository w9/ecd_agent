"""Turn the evidence ledger (and optional model text) into a QueryResponse."""

from __future__ import annotations

from typing import Any

from app.agent.tools import EvidenceLedger
from app.grounding import format_number, grounded_citations
from app.schemas import Citation, QueryResponse, Route, Source


def assemble(query: str, ledger: EvidenceLedger, model_answer: str | None) -> QueryResponse:
    if not ledger.used_site_tool and not ledger.used_protocol_tool:
        return QueryResponse(
            answer=_reject_answer(query, ledger.reject_reason or "unclear"),
            route="reject",
            source="none",
            citations=[],
        )

    route = _infer_route(ledger)
    if route == "protocol" and not ledger.protocol_chunks and not ledger.site_rows:
        return QueryResponse(
            answer="I don't have any information in the ingested protocols for that question.",
            route="protocol",
            source="none",
            citations=[],
        )
    if route == "hybrid" and not ledger.protocol_chunks and not ledger.site_rows:
        return QueryResponse(
            answer="I don't have enough protocol and site evidence to make a recommendation.",
            route="hybrid",
            source="none",
            citations=[],
        )
    if route == "site":
        site_response = _site_response(ledger, model_answer)
        if site_response is not None:
            return site_response

    citations = _citations(ledger)
    source = _infer_source(ledger, route)
    answer = (model_answer or "").strip() or _fallback_answer(ledger, route)
    answer = _pin_site_numbers(answer, ledger)
    return QueryResponse(answer=answer, route=route, source=source, citations=citations)


def should_short_circuit(ledger: EvidenceLedger) -> bool:
    """True when more model turns cannot change a deterministic outcome."""
    if _is_reject(ledger):
        return True
    if ledger.used_protocol_tool and not ledger.protocol_chunks and not ledger.used_site_tool:
        return True
    if not ledger.used_site_tool:
        return False
    if ledger.used_protocol_tool:
        return not ledger.protocol_chunks and not ledger.site_rows
    if _unknown_site(ledger):
        return True
    if _null_metric(ledger):
        return True
    if ledger.used_site_tool and not ledger.site_rows and not ledger.metric_results:
        return True
    return False


def _is_reject(ledger: EvidenceLedger) -> bool:
    if not ledger.reject_reason:
        return False
    return not ledger.used_site_tool and not ledger.used_protocol_tool


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


def _site_response(ledger: EvidenceLedger, model_answer: str | None) -> QueryResponse | None:
    if _unknown_site(ledger):
        site_id = _first_requested_site(ledger) or "that site"
        return QueryResponse(
            answer=f"I don't have any information on site {site_id}.",
            route="site",
            source="none",
            citations=[],
        )
    null_item = _null_metric(ledger)
    if null_item is not None:
        site_id = str(null_item.get("site_id") or "that site")
        field = str(null_item.get("field") or "metric")
        label = field.replace("_", " ")
        citations = [Citation(source="sites", site_id=site_id)]
        return QueryResponse(
            answer=f"The {label} for {site_id} is not available.",
            route="site",
            source="sites",
            citations=citations,
        )
    metric = _successful_metric(ledger)
    if metric is not None:
        site_id = str(metric["site_id"])
        field = str(metric["field"])
        value = metric["value"]
        return QueryResponse(
            answer=_format_metric_answer(site_id, field, value),
            route="site",
            source="sites",
            citations=[Citation(source="sites", site_id=site_id)],
        )
    if len(ledger.site_rows) == 1 and not _looks_like_ranking(ledger):
        row = ledger.site_rows[0]
        site_id = str(row.get("site_id") or "unknown")
        templated = _format_site_row(row)
        answer = (model_answer or "").strip()
        if site_id not in answer:
            answer = templated
        answer = _pin_site_numbers(answer, ledger)
        expected_numbers = [
            format_number(row[key])
            for key in ("monthly_enrollment_rate", "active_trials", "remaining_slots")
            if row.get(key) is not None
        ]
        if expected_numbers and not any(number in answer for number in expected_numbers):
            answer = templated
        return QueryResponse(
            answer=answer,
            route="site",
            source="sites",
            citations=[Citation(source="sites", site_id=site_id)],
        )
    if ledger.site_rows:
        top = ledger.site_rows[0]
        site_id = str(top.get("site_id") or "")
        rate = top.get("monthly_enrollment_rate")
        answer = (model_answer or "").strip()
        if site_id and site_id not in answer:
            area = top.get("therapeutic_area")
            area_text = f" among {str(area).lower()} sites" if area else ""
            rate_text = format_number(rate) if rate is not None else "an unknown rate"
            answer = f"{site_id} has the highest enrollment rate{area_text} at {rate_text}."
        else:
            answer = _pin_site_numbers(answer, ledger)
        citations = [
            Citation(source="sites", site_id=str(row["site_id"]))
            for row in ledger.site_rows
            if row.get("site_id")
        ]
        return QueryResponse(
            answer=answer or "I don't have any information to rank sites for that query.",
            route="site",
            source="sites",
            citations=citations[:1],
        )
    if ledger.used_site_tool:
        return QueryResponse(
            answer="I don't have any information to rank sites for that query.",
            route="site",
            source="none",
            citations=[],
        )
    return None


def _unknown_site(ledger: EvidenceLedger) -> bool:
    if ledger.site_rows:
        return False
    lookups = [item for item in ledger.metric_results if item.get("lookup") or item.get("field")]
    return bool(lookups) and all(not item.get("found") for item in lookups)


def _null_metric(ledger: EvidenceLedger) -> dict[str, Any] | None:
    for item in ledger.metric_results:
        if item.get("found") and item.get("field") and item.get("value") is None:
            return item
    return None


def _successful_metric(ledger: EvidenceLedger) -> dict[str, Any] | None:
    hits = [
        item
        for item in ledger.metric_results
        if item.get("found") and item.get("field") and item.get("value") is not None
    ]
    return hits[0] if len(hits) == 1 else None


def _first_requested_site(ledger: EvidenceLedger) -> str | None:
    for item in ledger.metric_results:
        site_id = item.get("site_id")
        if isinstance(site_id, str) and site_id:
            return site_id
    return None


def _looks_like_ranking(ledger: EvidenceLedger) -> bool:
    return len(ledger.site_rows) > 1


def _citations(ledger: EvidenceLedger) -> list[Citation]:
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
    seen_sites: set[str] = set()
    for row in ledger.site_rows:
        site_id = row.get("site_id")
        if not isinstance(site_id, str) or site_id in seen_sites:
            continue
        seen_sites.add(site_id)
        citations.append(Citation(source="sites", site_id=site_id))
    for item in ledger.metric_results:
        site_id = item.get("site_id")
        if item.get("found") and isinstance(site_id, str) and site_id not in seen_sites:
            seen_sites.add(site_id)
            citations.append(Citation(source="sites", site_id=site_id))
    return citations


def _fallback_answer(ledger: EvidenceLedger, route: Route) -> str:
    if route == "hybrid":
        return "Based on the retrieved protocol excerpts and site rows, see the cited sources."
    if route == "protocol" and ledger.protocol_chunks:
        return ledger.protocol_chunks[0].get("text") or "See the retrieved protocol excerpts."
    return "I don't have any information for that question."


def _pin_site_numbers(answer: str, ledger: EvidenceLedger) -> str:
    """Drop invented site IDs; keep tool numbers as the source of truth."""
    allowed_ids = {
        str(row["site_id"])
        for row in ledger.site_rows
        if row.get("site_id")
    }
    for item in ledger.metric_results:
        if item.get("found") and item.get("site_id"):
            allowed_ids.add(str(item["site_id"]))
    if not allowed_ids:
        return answer
    tokens = answer.split()
    kept: list[str] = []
    for token in tokens:
        stripped = token.strip(".,;:()[]")
        if stripped.upper().startswith("SITE-") and stripped.upper() not in {
            site_id.upper() for site_id in allowed_ids
        }:
            continue
        kept.append(token)
    return " ".join(kept)


def _format_metric_answer(site_id: str, field: str, value: float | int) -> str:
    number = format_number(value)
    if field == "monthly_enrollment_rate":
        return f"The monthly enrollment rate for {site_id} is {number}."
    if field == "active_trials":
        return f"There are {number} active trials at {site_id}."
    if field == "remaining_slots":
        return f"{site_id} has {number} remaining slots."
    return f"The {field.replace('_', ' ')} for {site_id} is {number}."


def _format_site_row(row: dict[str, Any]) -> str:
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


def _reject_answer(query: str, reason: str) -> str:
    if reason == "need_site":
        return "Please provide a site_id so I can look up that enrollment metric."
    if reason == "need_nct":
        return "Please provide an NCT ID for the study you want me to look up."
    if reason == "unsafe":
        lowered = query.lower()
        if "patient" in lowered or "chart" in lowered or "john doe" in lowered:
            return (
                "I can't process patient charts or give medical advice. "
                "Ask about a site_id or an NCT ID without personal health information."
            )
        if "protocol" in lowered:
            return (
                "I can't write a new clinical protocol from scratch. "
                "I can only answer questions about ingested public protocols and mock site data."
            )
        return "I can't help with that request."
    return "I need a more specific question about a site_id or an NCT ID / study."
