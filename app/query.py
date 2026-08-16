"""Run the tool-using agent and return a grounded QueryResponse."""

from __future__ import annotations

from pathlib import Path

from app.agent.loop import run_agent
from app.schemas import QueryRequest, QueryResponse


def handle_query(
    request: QueryRequest,
    *,
    sites_db_path: Path | str,
    protocols_db_path: Path | str,
) -> QueryResponse:
    return run_agent(
        request.query,
        request.nct_id,
        sites_db_path=sites_db_path,
        protocols_db_path=protocols_db_path,
    )
