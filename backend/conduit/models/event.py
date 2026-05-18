# SPDX-License-Identifier: MIT
"""Audit-event schema. Stored in SQLite, surfaced unchanged in the dashboard."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .classification import Classification, Decision, LTMatch


class ImageAnalysis(BaseModel):
    ui_type: str = "unknown"
    visible_sensitive_elements: list[dict[str, Any]] = Field(default_factory=list)
    extracted_text_snippet: str = ""
    suggest_text_alternative: bool = False


class ReasoningTrace(BaseModel):
    final_severity: str = "low"
    confirmed_categories: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    decision_change: str = "confirmed"  # confirmed | escalated | downgraded


class EventRecord(BaseModel):
    id: str
    timestamp: datetime
    destination: str
    user_pseudo_id: str
    page_title: str | None = None
    trigger: str = "paste"
    char_count: int = 0

    decision: Decision
    lt_match: LTMatch | None = None
    classification: Classification

    prompt_excerpt: str = Field(
        ...,
        description="First 240 chars of the prompt — used so the dashboard can show context without exposing the full prompt body.",
    )
    sanitized_excerpt: str | None = None

    override_applied: bool = False
    audit_message: str | None = None

    # Multimodal extensions
    is_image: bool = False
    image_mime: str | None = None
    image_analysis: ImageAnalysis | None = None

    # Thinking-mode escalation result (present only when Pro was consulted)
    reasoning: ReasoningTrace | None = None

    def to_dashboard_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class EventListResponse(BaseModel):
    events: list[EventRecord]
    next_cursor: str | None = None


class StatsSummary(BaseModel):
    total_events: int
    by_decision: dict[str, int]
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_destination: dict[str, int]
    overrides_applied: int
    window_hours: int = 24
