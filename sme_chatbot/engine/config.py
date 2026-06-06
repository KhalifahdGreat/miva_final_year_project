"""Engine configuration.

Single source of truth for the LLM/retrieval knobs the platform needs. Every
field has a sensible default so `EngineConfig()` works out of the box during
development; the application overrides only what it needs (see app/deps.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_PROJECT_ROOT = _PACKAGE_DIR.parent


@dataclass(frozen=True)
class EngineConfig:
    """Immutable configuration for a retrieval/LLM engine instance."""

    project_root: Path = _DEFAULT_PROJECT_ROOT

    # LLM (Groq-hosted Llama 3.3 70B by default).
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    llm_model: str = "llama-3.3-70b-versatile"

    # Vector store. Two modes:
    #   * Local dev  -> Milvus Lite, file-backed at `vector_db_path`.
    #   * Production -> managed Milvus (Zilliz Cloud): set `milvus_uri` +
    #                   `milvus_token`, which take precedence over the file.
    vector_db_path: Path | None = None
    milvus_uri: str = field(default_factory=lambda: os.getenv("MILVUS_URI", ""))
    milvus_token: str = field(default_factory=lambda: os.getenv("MILVUS_TOKEN", ""))
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval defaults.
    default_rag_top_k: int = 7
    min_search_score: float = 0.30

    # Collections searched when a caller does not specify any. For the SME
    # platform, retrieval is normally scoped to a per-tenant `kb_<id>`
    # collection passed explicitly, so this default is only a fallback.
    all_collections: tuple[str, ...] = ()

    @property
    def resolved_vector_db_path(self) -> Path:
        if self.vector_db_path is not None:
            return self.vector_db_path
        return self.project_root / "data" / "vectors.db"
