"""Deterministic tool-calling double for SPECS e2e tests.

Plans the same tools a well-behaved model should, then synthesizes the next
turn from real tool JSON so the agent loop and grounding stay under test.
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from app.llm import ChatResult, ToolCall

SITE_ID_RE = re.compile(r"\bSITE-\d+\b", re.IGNORECASE)
SITE_TOKEN_RE = re.compile(r"\bsite\s+([A-Za-z0-9-]+)\b", re.IGNORECASE)
NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)

_UNSAFE = (
    re.compile(r"write\s+(me\s+)?a\s+new\s+clinical\s+protocol", re.I),
    re.compile(r"from\s+scratch", re.I),
    re.compile(r"enroll\s+my\s+patient", re.I),
    re.compile(r"should\s+i\s+enroll", re.I),
    re.compile(r"patient\s+\w+.+\bchart", re.I),
    re.compile(r"\bphi\b", re.I),
    re.compile(r"john\s+doe", re.I),
)
_HYBRID = (
    re.compile(r"where\s+should\s+i\s+run", re.I),
    re.compile(r"next\s+.*\btrial", re.I),
    re.compile(r"recommend\s+(a\s+)?sites?", re.I),
    re.compile(r"given\s+this\s+protocol", re.I),
)
_PROTOCOL_LOOKALIKE = (
    re.compile(r"enrollment\s+criteria", re.I),
    re.compile(r"inclusion\s+criteria", re.I),
    re.compile(r"exclusion\s+criteria", re.I),
    re.compile(r"\beligibility\b", re.I),
)
_PROTOCOL = (
    re.compile(r"minimum\s+age", re.I),
    re.compile(r"maximum\s+age", re.I),
    re.compile(r"\bdosing\b", re.I),
    re.compile(r"\bcriteria\b", re.I),
    re.compile(r"\bprotocol\b", re.I),
    re.compile(r"\bnct\d{8}\b", re.I),
)
_SITE_RANK = re.compile(r"\bhighest\b.*\benrollment\b|\benrollment\b.*\bhighest\b", re.I)
_SITE = (
    re.compile(r"enrollment\s+rate", re.I),
    re.compile(r"active\s+trials", re.I),
    re.compile(r"remaining\s+slots", re.I),
    re.compile(r"tell\s+me\s+about\s+site", re.I),
    _SITE_RANK,
)


def scripted_chat(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> ChatResult:
    del tools
    query, nct_id = _user_payload(messages)
    if any(message.get("role") == "tool" for message in messages):
        return ChatResult(content=_synthesize(messages))
    return ChatResult(tool_calls=_plan(query, nct_id))


def _plan(query: str, nct_id: str | None) -> list[ToolCall]:
    nct_id = nct_id or _extract_nct(query)
    site_id = _extract_site_id(query)
    if any(pattern.search(query) for pattern in _UNSAFE):
        return [_call("reject", {"reason": "unsafe"})]
    if any(pattern.search(query) for pattern in _HYBRID):
        if not nct_id:
            return [_call("reject", {"reason": "need_nct"})]
        area = _extract_area(query)
        args: dict[str, Any] = {
            "field": "monthly_enrollment_rate",
            "limit": 4,
        }
        if area:
            args["therapeutic_area"] = area
        return [
            _call("search_protocol", {"query": query, "nct_id": nct_id}),
            _call("rank_sites", args),
        ]
    if any(pattern.search(query) for pattern in _PROTOCOL_LOOKALIKE):
        args = {"query": query}
        if nct_id:
            args["nct_id"] = nct_id
        return [_call("search_protocol", args)]
    if any(pattern.search(query) for pattern in _PROTOCOL):
        if not nct_id:
            return [_call("reject", {"reason": "need_nct"})]
        return [_call("search_protocol", {"query": query, "nct_id": nct_id})]
    if _SITE_RANK.search(query):
        args = {"field": "monthly_enrollment_rate", "limit": 1}
        area = _extract_area(query)
        if area:
            args["therapeutic_area"] = area
        return [_call("rank_sites", args)]
    if any(pattern.search(query) for pattern in _SITE) or site_id:
        if not site_id:
            return [_call("reject", {"reason": "need_site"})]
        field = _extract_field(query)
        if field:
            return [_call("get_site_metric", {"site_id": site_id, "field": field})]
        return [_call("lookup_site", {"site_id": site_id})]
    return [_call("reject", {"reason": "unclear"})]


def _synthesize(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(message.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("chunks"):
            for chunk in payload["chunks"]:
                if isinstance(chunk, dict) and chunk.get("text"):
                    parts.append(str(chunk["text"]))
        if payload.get("found") and payload.get("field"):
            parts.append(
                f"{payload.get('site_id')} {payload.get('field')} {payload.get('value')}"
            )
        site = payload.get("site")
        if payload.get("found") and isinstance(site, dict):
            parts.append(str(site))
        if isinstance(payload.get("sites"), list):
            parts.append(str(payload["sites"]))
    if not parts:
        return "I don't have that information."
    return "Grounded from tools: " + " ".join(parts)


def _user_payload(messages: list[dict[str, Any]]) -> tuple[str, str | None]:
    text = ""
    for message in messages:
        if message.get("role") == "user":
            text = str(message.get("content") or "")
    query = text
    nct_id = None
    if text.startswith("User question: "):
        body = text.removeprefix("User question: ")
        if "\nAttached NCT ID: " in body:
            query, attached = body.split("\nAttached NCT ID: ", 1)
            nct_id = attached.strip() or None
        else:
            query = body
    return query, nct_id


def _extract_site_id(query: str) -> str | None:
    match = SITE_ID_RE.search(query)
    if match:
        return match.group(0).upper()
    match = SITE_TOKEN_RE.search(query)
    if match:
        token = match.group(1)
        if token.upper().startswith("SITE-"):
            return token.upper()
        return token
    return None


def _extract_nct(query: str) -> str | None:
    match = NCT_RE.search(query)
    return match.group(0).upper() if match else None


def _extract_field(query: str) -> str | None:
    lowered = query.lower()
    if "remaining slot" in lowered:
        return "remaining_slots"
    if "active trial" in lowered:
        return "active_trials"
    if "enrollment rate" in lowered:
        return "monthly_enrollment_rate"
    return None


def _extract_area(query: str) -> str | None:
    match = re.search(
        r"\b(oncology|immunology|neurology|cardiology|respiratory|infectious disease)\b",
        query,
        re.IGNORECASE,
    )
    if not match:
        return None
    area = match.group(1).lower()
    if area == "infectious disease":
        return "Infectious Disease"
    return area.title()


def _call(name: str, arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(id=f"call_{uuid4().hex[:8]}", name=name, arguments=arguments)
