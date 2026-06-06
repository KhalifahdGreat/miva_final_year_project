"""Typed application settings loaded from environment variables.

Single source of truth for paths, API keys, and feature flags.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent.parent     # sme_chatbot/


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"

    # Database — real value comes from DATABASE_URL in the environment (.env).
    # The fallback intentionally carries no embedded credentials.
    database_url: str = "postgresql://localhost:5433/sme_chatbot"
    database_pool_min: int = 1
    database_pool_max: int = 10

    # Redis
    redis_url: str = "redis://localhost:6380/0"

    # Shared engine
    ofofo_vector_db_path: Path = Field(
        default=_PROJECT_ROOT.parent.parent / "milestone_two" / "db" / "ofofo_vectors.db"
    )
    ofofo_embedding_model: str = "all-MiniLM-L6-v2"

    # LLM
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: float = 10.0
    llm_max_retries: int = 3

    # WhatsApp
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    meta_graph_api_base: str = "https://graph.facebook.com/v20.0"

    # Widget
    widget_allowed_origins: str = "http://localhost:3000"

    # Object storage (Cloudflare R2)
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "sme-chatbot-uploads"

    # Observability (all optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    sentry_dsn: str = ""

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    @property
    def widget_origins_list(self) -> list[str]:
        return [o.strip() for o in self.widget_allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
