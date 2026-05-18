# SPDX-License-Identifier: MIT
"""Runtime config for the Conduit MCP server.

Reads from environment, falling back to localhost backend so a CISO can
`uvx conduit-mcp` against their already-running compose stack without any
extra wiring.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Where the FastAPI backend lives. The MCP server is a thin shell around it.
    CONDUIT_BACKEND_URL: str = "http://localhost:8001"

    # Transport selection: stdio (Claude Desktop) or http (remote agents / SSE).
    MCP_TRANSPORT: str = "stdio"
    MCP_HTTP_HOST: str = "0.0.0.0"
    MCP_HTTP_PORT: int = 8765

    # Optional shared-secret header for the HTTP transport — empty disables.
    MCP_AUTH_TOKEN: str = ""

    # Request timeouts on the upstream backend.
    BACKEND_TIMEOUT_SECONDS: float = 30.0


settings = Settings()
