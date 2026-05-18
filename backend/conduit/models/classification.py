# SPDX-License-Identifier: MIT
"""Schemas for Gemini's classification output and Lobster Trap's decision payload."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "source_code",
    "credentials",
    "customer_pii",
    "employee_pii",
    "financial_data",
    "strategic",
    "legal",
    "medical",
    "intellectual_property",
    "none",
]

Severity = Literal["low", "medium", "high", "critical"]
RegulatoryConcern = Literal["GDPR", "HIPAA", "SOX", "PCI-DSS", "trade_secret", "none"]
LTAction = Literal["ALLOW", "REDACT", "DENY", "FLAG"]


class SpecificFinding(BaseModel):
    type: str
    snippet_indicator: str = Field(..., max_length=20)
    rationale: str


class Classification(BaseModel):
    categories: list[Category] = Field(default_factory=lambda: ["none"])
    severity: Severity = "low"
    specific_findings: list[SpecificFinding] = Field(default_factory=list)
    explanation: str = ""
    suggest_sanitize: bool = False
    regulatory_concern: list[RegulatoryConcern] = Field(default_factory=lambda: ["none"])

    @classmethod
    def minimal_critical(cls, reason: str = "Lobster Trap hard-block") -> "Classification":
        return cls(
            categories=["credentials"],
            severity="critical",
            specific_findings=[],
            explanation=reason,
            suggest_sanitize=False,
            regulatory_concern=["none"],
        )

    @classmethod
    def benign(cls) -> "Classification":
        return cls(categories=["none"], severity="low", explanation="No sensitive content detected.")


class LTMatch(BaseModel):
    rule: str | None = None
    action: LTAction


class LTDecision(BaseModel):
    action: LTAction
    matched_rule: str | None = None
    redacted_body: str | None = None
    intent_classification: str | None = None
    detected_categories: list[str] = Field(default_factory=list)
    deny_message: str | None = None

    def as_match(self) -> LTMatch:
        return LTMatch(rule=self.matched_rule, action=self.action)


class InspectContext(BaseModel):
    destination: str
    user_pseudo_id: str = "anon"
    page_title: str | None = None
    trigger: Literal["paste", "submit", "manual", "image_paste", "image_drop", "agent"] = "paste"
    timestamp: str
    char_count: int = 0


class InspectRequest(BaseModel):
    prompt: str
    context: InspectContext


Decision = Literal["allow", "redact", "block"]


class InspectResponse(BaseModel):
    decision: Decision
    event_id: str
    lt_match: LTMatch | None = None
    classification: Classification
    sanitized_prompt: str | None = None
    audit_message: str | None = None
    # Optional thinking-mode escalation result.
    reasoning: dict | None = None


class ImageInspectRequest(BaseModel):
    image_b64: str = Field(..., description="Base64-encoded image bytes (no data: prefix)")
    image_mime: str = "image/png"
    context: InspectContext


class ImageInspectResponse(BaseModel):
    decision: Decision
    event_id: str
    classification: Classification
    image_analysis: dict
    sanitized_alternative: str | None = None
    audit_message: str | None = None
