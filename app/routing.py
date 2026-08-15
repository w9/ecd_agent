"""Deterministic query classification and entity extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import Route

SITE_ID_RE = re.compile(r"\bSITE-\d+\b", re.IGNORECASE)
SITE_TOKEN_RE = re.compile(r"\bsite\s+([A-Za-z0-9-]+)\b", re.IGNORECASE)
NCT_IN_TEXT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)

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


@dataclass(frozen=True)
class Classification:
    route: Route
    reason: str = ""


def classify(query: str) -> Classification:
    """Return exactly one route for a free-text query."""
    if any(pattern.search(query) for pattern in _UNSAFE):
        return Classification(route="reject", reason="unsafe")
    if any(pattern.search(query) for pattern in _HYBRID):
        return Classification(route="hybrid")
    if any(pattern.search(query) for pattern in _PROTOCOL_LOOKALIKE):
        return Classification(route="protocol")
    if any(pattern.search(query) for pattern in _SITE):
        return Classification(route="site")
    if any(pattern.search(query) for pattern in _PROTOCOL):
        return Classification(route="protocol")
    if extract_site_id(query):
        return Classification(route="site")
    return Classification(route="reject", reason="unclear")


def extract_site_id(query: str) -> str | None:
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


def extract_nct_id(query: str) -> str | None:
    match = NCT_IN_TEXT_RE.search(query)
    return match.group(0).upper() if match else None


def extract_metric_field(query: str) -> str | None:
    lowered = query.lower()
    if "remaining slot" in lowered:
        return "remaining_slots"
    if "active trial" in lowered:
        return "active_trials"
    if "enrollment rate" in lowered:
        return "monthly_enrollment_rate"
    return None


def is_ranking_query(query: str) -> bool:
    return bool(_SITE_RANK.search(query))


def extract_therapeutic_area(query: str) -> str | None:
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
