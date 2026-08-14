"""FastAPI application entrypoint.

Starter scaffold exposes only a health endpoint. Candidates add the main
query API, routing, RAG, and structured-data tool use during the exercise.
"""

from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Starter scaffold for a Clinical Site Feasibility AI Assistant. "
        "Extend this service during the timed interview exercise."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used to confirm the service starts cleanly."""
    return {"status": "ok"}
