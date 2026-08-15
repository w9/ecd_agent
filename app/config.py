"""Application settings.

Load configuration from environment variables (and an optional `.env` file).
Candidates can extend this module with LLM credentials, data paths, and
feature flags during the timed exercise.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the starter service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "clinical-site-feasibility"
    data_dir: Path = PROJECT_ROOT / "data"
    protocols_dir: Path = PROJECT_ROOT / "data" / "protocols"
    protocols_db_path: Path = PROJECT_ROOT / "data" / "protocols.db"
    sites_csv_path: Path = PROJECT_ROOT / "data" / "sites.csv"
    sites_db_path: Path = PROJECT_ROOT / "data" / "sites.db"

    # LLM / OpenRouter (protocol and hybrid answers)
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-5.6-luna"
    llm_provider: str = "openrouter"
    llm_debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
