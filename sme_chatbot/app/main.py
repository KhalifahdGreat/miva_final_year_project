"""FastAPI entrypoint.

    uvicorn app.main:app --reload --port 8000

Mounts all routers, configures logging, wires startup / shutdown hooks.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import (
    analytics,
    conversations,
    documents,
    tenants,
    webhooks,
    widget,
)

log = logging.getLogger(__name__)


def _configure_logging() -> None:
    s = get_settings()
    logging.basicConfig(
        level=s.app_log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan — open DB pool on startup, close on shutdown."""
    _configure_logging()
    log.info("starting sme-chatbot (env=%s)", get_settings().app_env)
    try:
        from .db import init_pool
        init_pool()
        log.info("postgres pool initialised")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not initialise postgres pool: %s (running degraded)", exc)
    yield
    log.info("shutting down")
    try:
        from .db import close_pool
        close_pool()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="SME Chatbot API",
    description=(
        "Multilingual customer-service chatbot for Nigerian SMEs. "
        "WhatsApp + web widget, multi-tenant, RAG-grounded over a 2 M-vector "
        "Nigerian corpus, served via Llama 3.3 70B on Groq."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — locked to widget origins + the Next.js dashboard (in dev).
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.widget_origins_list + ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(webhooks.router)
app.include_router(widget.router)
app.include_router(tenants.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(analytics.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": "SME Chatbot API",
        "version": "0.1.0",
        "docs": "/docs",
    }
