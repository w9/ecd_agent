"""FastAPI application: health check plus the feasibility query API."""

from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.llm import LLMError
from app.query import handle_query
from app.rag.parse import CachedProtocol, list_cached_protocols
from app.schemas import QueryRequest, QueryResponse

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Clinical Site Feasibility AI Assistant. "
        "Answers site-enrollment questions from structured data and "
        "protocol questions from retrieved public study text."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used to confirm the service starts cleanly."""
    return {"status": "ok"}


@app.get("/protocols")
def protocols() -> list[CachedProtocol]:
    """Cached study IDs for the chat UI NCT dropdown."""
    return list_cached_protocols(settings.protocols_dir)


@app.post("/query", response_model=QueryResponse, response_model_exclude_none=True)
def query(payload: QueryRequest) -> QueryResponse:
    """Run the tool-using agent on a free-text feasibility question."""
    try:
        return handle_query(
            payload,
            sites_db_path=settings.sites_db_path,
            protocols_db_path=settings.protocols_db_path,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc) or "LLM unavailable") from exc
