# SPDX-License-Identifier: MIT
"""Runtime configuration. All values read from env, with .env.example documenting them."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GEMINI_API_KEY: str = ""

    # Lobster Trap endpoints. CRITICAL: backend never points at Gemini directly.
    LT_INSPECT_URL: str = "http://lobster-trap:8000/_lobstertrap/inspect"
    LT_GEMINI_BASE_URL: str = "http://lobster-trap:8000/v1/"
    LT_POLICY_PATH: str = "/policies/policy.yaml"
    LT_MOCK_MODE: bool = False

    GEMINI_MODEL_CLASSIFY: str = "gemini-2.5-flash"
    GEMINI_MODEL_SANITIZE: str = "gemini-2.5-pro"
    GEMINI_MODEL_NARRATIVE: str = "gemini-2.5-pro"

    DB_PATH: str = "./data/events.db"
    BACKEND_PORT: int = 8001
    ALLOWED_ORIGINS: str = "chrome-extension://*,http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
