"""Flatten ClinicalTrials.gov study JSON into labeled plain-text sections.

Only protocol-narrative modules are extracted (eligibility, conditions,
interventions/arms, design, outcomes). Results tables, site lists, and PDF
pointers are ignored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ELIGIBILITY_HEADER = re.compile(
    r"^(inclusion criteria|exclusion criteria)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class ProtocolSection:
    """A labeled block of protocol text for one study."""

    nct_id: str
    brief_title: str
    section: str
    text: str


@dataclass(frozen=True)
class CachedProtocol:
    """Identity fields for a cached CT.gov JSON file, used by the dev chat UI."""

    nct_id: str
    brief_title: str


_NCT_FILENAME = re.compile(r"^NCT\d{8}$", re.IGNORECASE)


def parse_study_file(path: Path | str) -> list[ProtocolSection]:
    """Load a cached CT.gov JSON file and flatten useful sections."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_study(payload)


def parse_study(payload: dict[str, Any]) -> list[ProtocolSection]:
    """Flatten a CT.gov API v2 study document into labeled sections."""
    protocol = payload.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    nct_id = str(ident.get("nctId") or "").strip().upper()
    brief_title = str(ident.get("briefTitle") or "").strip()
    if not nct_id:
        raise ValueError("Study JSON is missing protocolSection.identificationModule.nctId")

    sections: list[ProtocolSection] = []

    def add(section: str, text: str) -> None:
        cleaned = _clean_text(text)
        if cleaned:
            sections.append(
                ProtocolSection(
                    nct_id=nct_id,
                    brief_title=brief_title,
                    section=section,
                    text=cleaned,
                )
            )

    add("conditions", _flatten_conditions(protocol.get("conditionsModule") or {}))
    add("design", _flatten_design(protocol.get("designModule") or {}))
    add("interventions.arms", _flatten_arms(protocol.get("armsInterventionsModule") or {}))
    add("interventions", _flatten_interventions(protocol.get("armsInterventionsModule") or {}))
    add("outcomes.primary", _flatten_outcomes(protocol.get("outcomesModule") or {}, "primaryOutcomes"))
    add("outcomes.secondary", _flatten_outcomes(protocol.get("outcomesModule") or {}, "secondaryOutcomes"))
    add("outcomes.other", _flatten_outcomes(protocol.get("outcomesModule") or {}, "otherOutcomes"))

    eligibility = protocol.get("eligibilityModule") or {}
    add("eligibility.structured", _flatten_eligibility_structured(eligibility))
    for name, text in _split_eligibility_criteria(eligibility.get("eligibilityCriteria") or ""):
        add(name, text)

    return sections


def iter_protocol_files(protocols_dir: Path | str) -> list[Path]:
    """Return cached study JSON paths in stable order."""
    directory = Path(protocols_dir)
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def list_cached_protocols(protocols_dir: Path | str) -> list[CachedProtocol]:
    """Return nct_id + brief title for each cached study JSON (skips unreadable files)."""
    found: list[CachedProtocol] = []
    for path in iter_protocol_files(protocols_dir):
        nct_id = ""
        brief_title = ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            ident = (payload.get("protocolSection") or {}).get("identificationModule") or {}
            nct_id = str(ident.get("nctId") or "").strip().upper()
            brief_title = str(ident.get("briefTitle") or "").strip()
        if not nct_id and _NCT_FILENAME.fullmatch(path.stem):
            nct_id = path.stem.upper()
        if nct_id:
            found.append(CachedProtocol(nct_id=nct_id, brief_title=brief_title))
    return found


def _flatten_conditions(module: dict[str, Any]) -> str:
    return _labeled_lines(
        ("Conditions", _join_list(module.get("conditions"))),
        ("Keywords", _join_list(module.get("keywords"))),
    )


def _flatten_design(module: dict[str, Any]) -> str:
    info = module.get("designInfo") or {}
    masking = info.get("maskingInfo") or {}
    enrollment = module.get("enrollmentInfo") or {}
    enrollment_count = enrollment.get("count")
    enrollment_type = enrollment.get("type")
    enrollment_text = None
    if enrollment_count is not None:
        enrollment_text = str(enrollment_count)
        if enrollment_type:
            enrollment_text = f"{enrollment_count} ({enrollment_type})"

    return _labeled_lines(
        ("Study type", module.get("studyType")),
        ("Phases", _join_list(module.get("phases"))),
        ("Allocation", info.get("allocation")),
        ("Intervention model", info.get("interventionModel")),
        ("Intervention model description", info.get("interventionModelDescription")),
        ("Primary purpose", info.get("primaryPurpose")),
        ("Masking", masking.get("masking")),
        ("Masking description", masking.get("maskingDescription")),
        ("Who masked", _join_list(masking.get("whoMasked"))),
        ("Enrollment", enrollment_text),
    )


def _flatten_arms(module: dict[str, Any]) -> str:
    blocks: list[str] = []
    for arm in module.get("armGroups") or []:
        block = _labeled_lines(
            ("Arm", arm.get("label")),
            ("Type", arm.get("type")),
            ("Description", arm.get("description")),
            ("Interventions", _join_list(arm.get("interventionNames"))),
        )
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def _flatten_interventions(module: dict[str, Any]) -> str:
    blocks: list[str] = []
    for item in module.get("interventions") or []:
        block = _labeled_lines(
            ("Intervention", item.get("name")),
            ("Type", item.get("type")),
            ("Description", item.get("description")),
            ("Arm groups", _join_list(item.get("armGroupLabels"))),
            ("Other names", _join_list(item.get("otherNames"))),
        )
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def _flatten_outcomes(module: dict[str, Any], key: str) -> str:
    blocks: list[str] = []
    kind = key.replace("Outcomes", "").replace("other", "Other").title()
    for item in module.get(key) or []:
        block = _labeled_lines(
            (f"{kind} outcome", item.get("measure")),
            ("Description", item.get("description")),
            ("Time frame", item.get("timeFrame")),
        )
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def _flatten_eligibility_structured(module: dict[str, Any]) -> str:
    healthy = module.get("healthyVolunteers")
    healthy_text = None
    if isinstance(healthy, bool):
        healthy_text = "yes" if healthy else "no"
    elif healthy is not None:
        healthy_text = str(healthy)

    return _labeled_lines(
        ("Healthy volunteers", healthy_text),
        ("Sex", module.get("sex")),
        ("Minimum age", module.get("minimumAge")),
        ("Maximum age", module.get("maximumAge")),
        ("Standard age groups", _join_list(module.get("stdAges"))),
    )


def _split_eligibility_criteria(raw: str) -> list[tuple[str, str]]:
    text = _clean_text(str(raw or ""))
    if not text:
        return []

    matches = list(_ELIGIBILITY_HEADER.finditer(text))
    if not matches:
        return [("eligibility.criteria", text)]

    parts: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        parts.append(("eligibility.criteria", preamble))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        if not body:
            continue
        header = match.group(1).lower()
        name = (
            "eligibility.inclusion"
            if header.startswith("inclusion")
            else "eligibility.exclusion"
        )
        parts.append((name, body))
    return parts


def _labeled_lines(*pairs: tuple[str, Any]) -> str:
    lines: list[str] = []
    for label, value in pairs:
        if value is None:
            continue
        rendered = str(value).strip()
        if not rendered:
            continue
        lines.append(f"{label}: {rendered}")
    return "\n".join(lines)


def _join_list(values: Any) -> str | None:
    if not values:
        return None
    if isinstance(values, str):
        return values
    parts = [str(item).strip() for item in values if str(item).strip()]
    return ", ".join(parts) if parts else None


def _clean_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"^[ \t]*\\-\s*", "- ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
