# SPDX-License-Identifier: MIT
"""Tiny aiosqlite session layer. SQLite is the right call for a hackathon-scale audit log."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from ..config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def _ensure_dir(path: str) -> None:
    p = Path(path).parent
    p.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    """Create the events table on first boot."""
    await _ensure_dir(settings.DB_PATH)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        with open(_SCHEMA_PATH) as f:
            await db.executescript(f.read())
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def loads(s: str | None, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return default


def reset_for_tests() -> None:
    """Remove the SQLite file. Called by the test harness only."""
    try:
        os.remove(settings.DB_PATH)
    except FileNotFoundError:
        pass
