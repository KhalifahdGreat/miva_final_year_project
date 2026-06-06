"""LLM client.

Centralised Groq wrapper. Every module that needs an LLM completion calls
through here so API-key management, retries, and error handling live in one
place.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import EngineConfig

log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = (1.0, 3.0, 8.0)


class LLMClient:
    """Thin wrapper around the Groq SDK chat-completions endpoint."""

    def __init__(self, config: EngineConfig) -> None:
        self._api_key = config.groq_api_key
        self._model = config.llm_model
        self._groq = None

    def _client(self):
        if self._groq is None:
            from groq import Groq

            self._groq = Groq(api_key=self._api_key)
        return self._groq

    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.72,
        max_tokens: int = 280,
    ) -> str:
        """Send a chat completion and return the assistant text.

        Retries on transient errors (rate-limit, 5xx) up to ``_MAX_RETRIES``
        times with exponential backoff.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client().chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=max(0.3, min(1.0, temperature)),
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                last_err = exc
                err_str = str(exc).lower()
                retryable = any(
                    t in err_str
                    for t in ("rate_limit", "429", "503", "502", "500", "timeout", "connection")
                )
                if retryable and attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF[attempt]
                    log.warning(
                        "LLM retry %d/%d after %.1fs: %s", attempt + 1, _MAX_RETRIES, wait, exc
                    )
                    time.sleep(wait)
                    continue
                raise

        raise last_err  # type: ignore[misc]
