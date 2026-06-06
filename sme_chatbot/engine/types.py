"""Shared value types for the retrieval engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SearchHit:
    """A single semantic-search result returned by the RetrievalService."""

    text: str = ""
    source: str = ""
    section: str = ""
    author: str = ""
    date: str = ""
    score: float = 0.0
    collection: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
