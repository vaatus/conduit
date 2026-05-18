# SPDX-License-Identifier: MIT
"""Thin async HTTP client for the Conduit FastAPI backend.

The MCP server is intentionally a shell — the backend remains the single source
of truth for inspection, audit, and policy. Keeps the backend ↔ MCP contract
narrow and means an org can run Conduit without MCP, or MCP without re-deploying
the backend.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .config import settings


class BackendError(RuntimeError):
    """Raised when the backend returns a non-2xx or is unreachable."""


class ConduitBackend:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.CONDUIT_BACKEND_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=settings.BACKEND_TIMEOUT_SECONDS)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            c = await self._http()
            r = await c.get(path, params=params or {})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise BackendError(f"GET {path} → {exc}") from exc

    async def _post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> Any:
        try:
            c = await self._http()
            r = await c.post(path, json=json_body, params=params or {})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise BackendError(f"POST {path} → {exc}") from exc

    # ─── High-level wrappers, one per MCP tool ────────────────────────

    async def inspect(self, prompt: str, destination: str = "manual", trigger: str = "manual",
                      user_pseudo_id: str = "mcp_agent", timestamp: str | None = None) -> dict:
        from datetime import datetime, timezone
        body = {
            "prompt": prompt,
            "context": {
                "destination": destination,
                "user_pseudo_id": user_pseudo_id,
                "page_title": None,
                "trigger": trigger,
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
                "char_count": len(prompt),
            },
        }
        return await self._post("/inspect", body)

    async def list_events(self, limit: int = 50, after: str | None = None,
                          decision: str | None = None, destination: str | None = None) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if after: params["after"] = after
        if decision: params["decision"] = decision
        if destination: params["destination"] = destination
        return await self._get("/events", params=params)

    async def get_event(self, event_id: str) -> dict:
        return await self._get(f"/events/{event_id}")

    async def stats(self, window_hours: int = 24) -> dict:
        return await self._get("/stats", params={"window_hours": window_hours})

    async def narrative(self, window_hours: int = 24) -> dict:
        return await self._post("/stats/narrative", params={"window_hours": window_hours})

    async def policy_rules(self) -> dict:
        return await self._get("/policy/rules")

    async def mark_override(self, event_id: str) -> dict:
        return await self._post("/inspect/override", params={"event_id": event_id})

    async def health(self) -> dict:
        return await self._get("/health")

    # ─── Gemini-heavy extensions ──────────────────────────────────────

    async def inspect_image(self, image_b64: str, image_mime: str = "image/png",
                            destination: str = "manual", trigger: str = "manual") -> dict:
        from datetime import datetime, timezone
        body = {
            "image_b64": image_b64,
            "image_mime": image_mime,
            "context": {
                "destination": destination,
                "user_pseudo_id": "mcp_agent",
                "page_title": None,
                "trigger": trigger,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "char_count": 0,
            },
        }
        return await self._post("/inspect/image", body)

    async def similar_events(self, event_id: str, k: int = 5) -> dict:
        return await self._get(f"/events/{event_id}/similar", params={"k": k})

    async def threat_intel(self, event_id: str) -> dict:
        return await self._post(f"/events/{event_id}/enrich/threat-intel")

    async def agentic_narrative(self, window_hours: int = 24) -> dict:
        return await self._post("/stats/narrative/agentic", params={"window_hours": window_hours})


# Module-level singleton so MCP tool registrations share one client.
backend = ConduitBackend()


def pretty(obj: Any) -> str:
    """Format any backend payload as compact, agent-friendly JSON."""
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
