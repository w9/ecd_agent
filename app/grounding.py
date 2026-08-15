"""Keep answers and citations inside retrieved / tool evidence."""

from __future__ import annotations

from typing import Any, Iterable

from app.schemas import Citation


def must_abstain(hits: Iterable[object] | None, tool_result: object | None) -> bool:
    """True when there is no retrieved chunk and no structured tool row."""
    return not bool(hits) and tool_result is None


def grounded_citations(
    citations: list[Citation] | list[dict[str, Any]],
    hits: list[object],
) -> list[Citation]:
    """Drop protocol citations whose nct_id/section was not retrieved."""
    allowed: set[tuple[str, str]] = set()
    for hit in hits:
        nct_id = _value(hit, "nct_id")
        section = _value(hit, "section")
        if nct_id and section:
            allowed.add((str(nct_id).upper(), str(section)))

    kept: list[Citation] = []
    for citation in citations:
        item = citation if isinstance(citation, Citation) else Citation.model_validate(citation)
        if item.source != "protocol":
            kept.append(item)
            continue
        if item.nct_id and item.section and (item.nct_id.upper(), item.section) in allowed:
            kept.append(item)
    return kept


def format_number(value: float | int) -> str:
    """Render a DB number the way SPECS examples do (8.3, 0, 24)."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value == 0:
            return "0"
        rendered = f"{value:.10f}".rstrip("0").rstrip(".")
        return rendered
    return str(value)


def _value(item: object, key: str) -> object:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
