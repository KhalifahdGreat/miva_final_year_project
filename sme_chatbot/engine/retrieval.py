"""Vector retrieval.

Instance-based wrapper around Milvus Lite and SentenceTransformers. No
module-level singletons — each ``RetrievalService`` owns its connections.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .types import SearchHit

if TYPE_CHECKING:
    from .config import EngineConfig

log = logging.getLogger(__name__)


class RetrievalService:
    """Semantic search over a Milvus-Lite vector database."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._model = None
        self._client = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._config.embedding_model)
        return self._model

    def _ensure_client(self):
        if self._client is None:
            from pymilvus import MilvusClient

            # Managed Milvus (Zilliz Cloud) takes precedence when configured;
            # otherwise fall back to a local file-backed Milvus Lite database.
            if self._config.milvus_uri:
                self._client = MilvusClient(
                    uri=self._config.milvus_uri,
                    token=self._config.milvus_token,
                )
            else:
                path = self._config.resolved_vector_db_path
                path.parent.mkdir(parents=True, exist_ok=True)
                self._client = MilvusClient(str(path))
        return self._client

    @property
    def model(self):
        return self._ensure_model()

    @property
    def client(self):
        return self._ensure_client()

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        collections: list[str] | None = None,
        top_k: int = 5,
        min_score: float | None = None,
    ) -> list[SearchHit]:
        if collections is None:
            collections = list(self._config.all_collections)
        if min_score is None:
            min_score = self._config.min_search_score

        model = self._ensure_model()
        client = self._ensure_client()
        query_embedding = model.encode([query], normalize_embeddings=True)[0].tolist()

        all_results: list[SearchHit] = []

        for coll_name in collections:
            try:
                results = client.search(
                    collection_name=coll_name,
                    data=[query_embedding],
                    limit=top_k,
                    output_fields=[
                        "text",
                        "source",
                        "section",
                        "author",
                        "date",
                        "metadata_json",
                    ],
                    search_params={"metric_type": "COSINE"},
                )
                for hits in results:
                    for hit in hits:
                        score = hit.get("distance", 0)
                        if score < min_score:
                            continue
                        entity = hit.get("entity", {})
                        meta: dict = {}
                        try:
                            meta = json.loads(entity.get("metadata_json", "{}"))
                        except Exception:
                            pass
                        all_results.append(
                            SearchHit(
                                text=entity.get("text", ""),
                                source=entity.get("source", ""),
                                section=entity.get("section", ""),
                                author=entity.get("author", ""),
                                date=entity.get("date", ""),
                                score=round(score, 4),
                                collection=coll_name,
                                metadata=meta,
                            )
                        )
            except Exception as exc:
                log.warning("search in %s failed: %s", coll_name, exc)

        all_results.sort(key=lambda h: h.score, reverse=True)
        return all_results[:top_k]

    # ------------------------------------------------------------------
    # Formatting helper
    # ------------------------------------------------------------------

    @staticmethod
    def format_as_context(hits: list[SearchHit], max_items: int = 5) -> str:
        lines: list[str] = []
        for h in hits[:max_items]:
            label = f"{h.source}, {h.section}" if h.section else h.source
            preview = h.text[:500].replace("\n", " ")
            lines.append(f'- "{preview}" ({label})')
        return "\n".join(lines)
