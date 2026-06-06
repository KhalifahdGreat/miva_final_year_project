"""Core engine — pure Python, no FastAPI imports.

This package is the language-handling and orchestration brain. It is callable
from a CLI, a Jupyter notebook, the FastAPI app, or a background worker.
"""

from .types import (
    CanonicalMessage,
    EscalationRule,
    Hit,
    OrchestrationResult,
    TenantConfig,
    Turn,
)

__all__ = [
    "CanonicalMessage",
    "EscalationRule",
    "Hit",
    "OrchestrationResult",
    "TenantConfig",
    "Turn",
]
