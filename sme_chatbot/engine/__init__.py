"""Self-contained retrieval + LLM engine for the SME chatbot.

This package is a trimmed, standalone vendoring of the three components the
platform reuses: an immutable `EngineConfig`, a thin Groq `LLMClient`, and a
Milvus-Lite `RetrievalService`. It carries no dependency on any parent
project, so the service deploys as a self-contained repository.
"""

from .config import EngineConfig
from .llm import LLMClient
from .retrieval import RetrievalService
from .types import SearchHit

__all__ = ["EngineConfig", "LLMClient", "RetrievalService", "SearchHit"]
