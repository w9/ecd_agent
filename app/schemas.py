"""Request and response models for POST /query."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_QUERY_LENGTH = 8000
NCT_ID_RE = re.compile(r"^NCT\d{8}$")

Route = Literal["site", "protocol", "hybrid", "reject"]
Source = Literal["sites", "protocol", "hybrid", "none"]


class QueryRequest(BaseModel):
    query: str
    nct_id: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_be_usable(cls, value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("query must be non-empty")
        if len(value) > MAX_QUERY_LENGTH:
            raise ValueError(f"query must be at most {MAX_QUERY_LENGTH} characters")
        return value.strip()

    @field_validator("nct_id")
    @classmethod
    def nct_id_must_be_well_formed(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = str(value).strip().upper()
        if not NCT_ID_RE.fullmatch(normalized):
            raise ValueError("nct_id must be NCT followed by 8 digits")
        return normalized


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["sites", "protocol"]
    site_id: str | None = None
    nct_id: str | None = None
    section: str | None = None


class LlmDebugExchange(BaseModel):
    request: dict[str, Any]
    response: dict[str, Any]


class QueryResponse(BaseModel):
    answer: str
    route: Route
    source: Source
    citations: list[Citation] = Field(default_factory=list)
    llm_debug: list[LlmDebugExchange] | None = None
