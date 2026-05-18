# SPDX-License-Identifier: MIT
"""FastAPI app entrypoint for Conduit's backend."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.session import init_db
from .routes import events, health, inspect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Conduit Backend",
    version="0.1.0",
    description="Shadow-AI governance: inspects every prompt headed to a public LLM through Veea Lobster Trap + Gemini.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["meta"])
app.include_router(inspect.router, tags=["inspect"])
app.include_router(events.router, tags=["events"])


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/")
async def root():
    return {
        "name": "conduit-backend",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": ["/inspect", "/events", "/events/{id}", "/stats", "/stats/narrative", "/policy/rules", "/health"],
    }
