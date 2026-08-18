"""Allowlisted tools the feasibility agent may call."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import QueryResponse
from app.tools.protocols import get_protocol_field, search_protocol
from app.tools.sites import (
    FILTER_COMPARE_FIELDS,
    FILTER_EQ_FIELDS,
    FILTER_OPS,
    SITE_FIELDS,
    filter_sites,
    list_sites,
    lookup_site,
    rank_sites,
)

FILTER_FIELDS = FILTER_EQ_FIELDS | FILTER_COMPARE_FIELDS
MAX_FILTER_LIMIT = 50

METRIC_FIELDS = frozenset(
    {"monthly_enrollment_rate", "active_trials", "remaining_slots"}
)
RANK_FIELDS = frozenset(SITE_FIELDS) - {"site_id", "site_name", "country", "region", "therapeutic_area"}
MAX_RANK_LIMIT = 12

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_site",
            "description": "Return the full mock site row for a site_id, or not found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {
                        "type": "string",
                        "description": "Site identifier, e.g. SITE-001 or YYY.",
                    }
                },
                "required": ["site_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_site_metric",
            "description": (
                "Return one numeric site field. value is null when the site "
                "exists but that metric is missing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "string"},
                    "field": {
                        "type": "string",
                        "enum": sorted(METRIC_FIELDS),
                    },
                },
                "required": ["site_id", "field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_sites",
            "description": "Rank sites by a numeric field, highest first. Skips nulls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": sorted(RANK_FIELDS),
                        "default": "monthly_enrollment_rate",
                    },
                    "therapeutic_area": {
                        "type": "string",
                        "description": "Optional filter, e.g. Oncology.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_RANK_LIMIT,
                        "default": 5,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sites",
            "description": "List mock site rows, optionally filtered by therapeutic area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "therapeutic_area": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_sites",
            "description": (
                "Return a page of site rows matching AND filters. "
                "Use for 'all sites that are …'. Equality on country, region, "
                "or therapeutic_area; comparisons on numeric fields. "
                "Keep list_sites for an unpaged therapeutic-area dump."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "array",
                        "description": "AND predicates. Empty or omitted returns all sites.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "enum": sorted(FILTER_FIELDS),
                                },
                                "op": {
                                    "type": "string",
                                    "enum": sorted(FILTER_OPS),
                                },
                                "value": {
                                    "description": "String for categorical eq; number for numeric ops.",
                                },
                            },
                            "required": ["field", "op", "value"],
                        },
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_FILTER_LIMIT,
                        "default": 20,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_protocol",
            "description": (
                "Retrieve ingested protocol chunks. Pass nct_id when known; "
                "omit nct_id if unknown. site_id is not a filter and does not "
                "bind chunks to a site. For eligibility questions, search with "
                "inclusion/exclusion/eligibility terms, not the raw utterance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Eligibility or scientific terms to search. "
                            "Do not include a site_id."
                        ),
                    },
                    "nct_id": {
                        "type": "string",
                        "description": "NCT followed by 8 digits, if known. Omit if unknown.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_protocol_field",
            "description": (
                "Extract one nested field from the stored raw ClinicalTrials.gov "
                "JSON via json_extract. Pass a JSON path such as "
                "$.protocolSection.eligibilityModule.minimumAge. "
                "Omit nct_id to return that field for every ingested study."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "JSON path. Leading $ is optional; "
                            "protocolSection.eligibilityModule.sex is also valid."
                        ),
                    },
                    "nct_id": {
                        "type": "string",
                        "description": "NCT followed by 8 digits. Omit to query every study.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "respond",
            "description": (
                "Submit the final API payload. Call this after tools, or "
                "immediately to refuse. You set answer, route, source, and "
                "citations. Copy site numbers from tools. Do not invent "
                "site IDs. Do not bind protocol chunks to a site_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "route": {
                        "type": "string",
                        "enum": ["site", "protocol", "hybrid", "reject"],
                    },
                    "source": {
                        "type": "string",
                        "enum": ["sites", "protocol", "hybrid", "none"],
                    },
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {
                                    "type": "string",
                                    "enum": ["sites", "protocol"],
                                },
                                "site_id": {"type": "string"},
                                "nct_id": {"type": "string"},
                                "section": {"type": "string"},
                            },
                            "required": ["source"],
                        },
                    },
                },
                "required": ["answer", "route", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject",
            "description": (
                "Mark the question as unsafe, incomplete, or out of scope. "
                "You must still call respond with route=reject."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": ["unsafe", "need_site", "need_nct", "unclear"],
                    }
                },
                "required": ["reason"],
            },
        },
    },
]


@dataclass
class ToolContext:
    sites_db_path: Path | str
    protocols_db_path: Path | str


@dataclass
class EvidenceLedger:
    site_rows: list[dict[str, Any]] = field(default_factory=list)
    metric_results: list[dict[str, Any]] = field(default_factory=list)
    protocol_chunks: list[dict[str, Any]] = field(default_factory=list)
    protocol_scoped_to_nct: bool = False
    reject_reason: str | None = None
    used_site_tool: bool = False
    used_protocol_tool: bool = False
    submitted: dict[str, Any] | None = None

    def record(self, name: str, payload: dict[str, Any]) -> None:
        if payload.get("error"):
            return
        if name == "respond":
            self.submitted = payload
            return
        if name == "reject":
            reason = payload.get("reason")
            if isinstance(reason, str):
                self.reject_reason = reason
            return
        if name in {"search_protocol", "get_protocol_field"}:
            self.used_protocol_tool = True
            if payload.get("scoped_to_nct") or payload.get("nct_id"):
                self.protocol_scoped_to_nct = True
            chunks = payload.get("chunks")
            if isinstance(chunks, list):
                self.protocol_chunks.extend(
                    chunk for chunk in chunks if isinstance(chunk, dict)
                )
            return
        if name in {
            "lookup_site",
            "get_site_metric",
            "rank_sites",
            "list_sites",
            "filter_sites",
        }:
            self.used_site_tool = True
        if name == "lookup_site":
            site = payload.get("site")
            if payload.get("found") and isinstance(site, dict):
                self.site_rows.append(site)
            self.metric_results.append(
                {
                    "found": bool(payload.get("found")),
                    "site_id": payload.get("site_id") or (site or {}).get("site_id"),
                    "field": None,
                    "value": None,
                    "lookup": True,
                }
            )
            return
        if name == "get_site_metric":
            self.metric_results.append(
                {
                    "found": bool(payload.get("found")),
                    "site_id": payload.get("site_id"),
                    "field": payload.get("field"),
                    "value": payload.get("value"),
                    "lookup": False,
                }
            )
            return
        if name in {"rank_sites", "list_sites", "filter_sites"}:
            sites = payload.get("sites")
            if isinstance(sites, list):
                self.site_rows.extend(row for row in sites if isinstance(row, dict))


def execute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Run one allowlisted tool. Unknown names and bad args become error payloads."""
    handlers = {
        "lookup_site": _lookup_site,
        "get_site_metric": _get_site_metric,
        "rank_sites": _rank_sites,
        "list_sites": _list_sites,
        "filter_sites": _filter_sites,
        "search_protocol": _search_protocol,
        "get_protocol_field": _get_protocol_field,
        "respond": _respond,
        "reject": _reject,
    }
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return handler(arguments, ctx)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}


def _lookup_site(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    site_id = _require_str(arguments, "site_id")
    row = lookup_site(site_id, db_path=ctx.sites_db_path)
    if row is None:
        return {"found": False, "site_id": site_id, "site": None}
    return {"found": True, "site_id": row["site_id"], "site": row}


def _get_site_metric(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    site_id = _require_str(arguments, "site_id")
    field = _require_str(arguments, "field")
    if field not in METRIC_FIELDS:
        raise ValueError(f"unsupported site field: {field}")
    row = lookup_site(site_id, db_path=ctx.sites_db_path)
    if row is None:
        return {"found": False, "site_id": site_id, "field": field, "value": None}
    return {
        "found": True,
        "site_id": row["site_id"],
        "field": field,
        "value": row.get(field),
    }


def _rank_sites(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    field = arguments.get("field") or "monthly_enrollment_rate"
    if not isinstance(field, str) or field not in RANK_FIELDS:
        raise ValueError(f"unsupported rank field: {field}")
    area = _optional_str(arguments, "therapeutic_area")
    limit = _optional_int(arguments, "limit", default=5)
    limit = max(1, min(limit, MAX_RANK_LIMIT))
    sites = rank_sites(
        db_path=ctx.sites_db_path,
        field=field,
        therapeutic_area=area,
        limit=limit,
    )
    return {"sites": sites, "field": field, "therapeutic_area": area}


def _list_sites(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    area = _optional_str(arguments, "therapeutic_area")
    return {"sites": list_sites(db_path=ctx.sites_db_path, therapeutic_area=area)}


def _filter_sites(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    filters = arguments.get("filters") or []
    if not isinstance(filters, list):
        raise ValueError("filters must be an array")
    offset = _optional_int(arguments, "offset", default=0)
    limit = _optional_int(arguments, "limit", default=20)
    if offset < 0:
        raise ValueError("offset must be >= 0")
    limit = max(1, min(limit, MAX_FILTER_LIMIT))
    return filter_sites(
        db_path=ctx.sites_db_path,
        filters=filters,
        offset=offset,
        limit=limit,
    )


def _search_protocol(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    query = _require_str(arguments, "query")
    nct_id = _optional_str(arguments, "nct_id")
    if nct_id:
        nct_id = nct_id.strip().upper()
    chunks = search_protocol(query, db_path=ctx.protocols_db_path, nct_id=nct_id)
    return {
        "chunks": chunks,
        "nct_id": nct_id,
        "scoped_to_nct": bool(nct_id),
        "site_bound": False,
        "note": (
            "Chunks are not associated with a site_id. "
            "search_protocol has no site filter. "
            "If scoped_to_nct is false and chunks span multiple studies, "
            "ask for an NCT ID instead of merging them."
        ),
    }


def _get_protocol_field(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    path = _require_str(arguments, "path")
    nct_id = _optional_str(arguments, "nct_id")
    if nct_id:
        nct_id = nct_id.strip().upper()
    return get_protocol_field(path, db_path=ctx.protocols_db_path, nct_id=nct_id)


def _respond(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    del ctx
    answer = arguments.get("answer")
    if not isinstance(answer, str):
        raise ValueError("answer must be a string")
    route = _require_str(arguments, "route")
    source = _require_str(arguments, "source")
    citations = arguments.get("citations") or []
    try:
        response = QueryResponse(answer=answer, route=route, source=source, citations=citations)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "submitted": True,
        "answer": response.answer,
        "route": response.route,
        "source": response.source,
        "citations": [citation.model_dump() for citation in response.citations],
    }


def _reject(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    del ctx
    reason = _require_str(arguments, "reason")
    if reason not in {"unsafe", "need_site", "need_nct", "unclear"}:
        raise ValueError(f"unsupported reject reason: {reason}")
    return {"rejected": True, "reason": reason}


def _require_str(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_str(arguments: dict[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    stripped = value.strip()
    return stripped or None


def _optional_int(arguments: dict[str, Any], key: str, *, default: int) -> int:
    value = arguments.get(key, default)
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"{key} must be an integer")
