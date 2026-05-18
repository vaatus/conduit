# SPDX-License-Identifier: MIT
"""The hot path: POST /inspect (text) and POST /inspect/image (vision).

Orchestrates seven Gemini surfaces:
  • classify          — text classification (Flash, JSON mode)
  • sanitize          — text rewrite (Pro)
  • classify_image    — image classification (Flash, vision input)
  • describe_image    — text alternative for a screenshot (Pro)
  • think_about       — thinking-mode escalation for ambiguous cases (Pro)
  • embed             — gemini-embedding-001 for similarity clustering
  (narrate/agentic live in routes/events.py)
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from ..db.session import dumps, get_db
from ..inspector import gemini
from ..inspector.lobster_trap import block_message, inspect_prompt
from ..models.classification import (
    Classification,
    Decision,
    ImageInspectRequest,
    ImageInspectResponse,
    InspectRequest,
    InspectResponse,
    LTDecision,
)
from ..models.event import EventRecord, ImageAnalysis, ReasoningTrace

router = APIRouter()

EXCERPT_LEN = 240


def _new_event_id() -> str:
    return "evt_" + secrets.token_hex(10)


def _excerpt(s: str | None) -> str | None:
    if s is None:
        return None
    return s[:EXCERPT_LEN]


def _summarize_findings(c: Classification) -> str:
    if not c.specific_findings and not c.categories:
        return "Sensitive content detected. Sanitized version preserves your question."
    cats = ", ".join(cat for cat in c.categories if cat != "none") or "sensitive content"
    return f"{cats.title()} detected. Sanitized version preserves your question."


def _is_ambiguous(lt: LTDecision, c: Classification) -> bool:
    """Escalate to thinking mode when Flash + LT disagree or the classification
    sits on the medium/high boundary — exactly where reasoning helps most."""
    if c.severity == "medium":
        return True
    # LT flagged but Flash said benign — Pro should adjudicate.
    if lt.action == "FLAG" and c.severity == "low":
        return True
    return False


async def _persist_event(
    *,
    req_context_dict: dict[str, Any],
    prompt_excerpt: str,
    decision: Decision,
    lt: LTDecision | None,
    classification: Classification,
    sanitized: str | None,
    audit_message: str | None,
    is_image: bool = False,
    image_mime: str | None = None,
    image_analysis: dict[str, Any] | None = None,
    reasoning: dict[str, Any] | None = None,
    embedding_b64: str = "",
) -> EventRecord:
    event_id = _new_event_id()
    record = EventRecord(
        id=event_id,
        timestamp=datetime.now(timezone.utc),
        destination=req_context_dict["destination"],
        user_pseudo_id=req_context_dict.get("user_pseudo_id", "anon"),
        page_title=req_context_dict.get("page_title"),
        trigger=req_context_dict.get("trigger", "paste"),
        char_count=req_context_dict.get("char_count") or len(prompt_excerpt),
        decision=decision,
        lt_match=lt.as_match() if lt else None,
        classification=classification,
        prompt_excerpt=prompt_excerpt or "",
        sanitized_excerpt=_excerpt(sanitized),
        override_applied=False,
        audit_message=audit_message,
        is_image=is_image,
        image_mime=image_mime,
        image_analysis=ImageAnalysis(**image_analysis) if image_analysis else None,
        reasoning=ReasoningTrace(**{k: v for k, v in (reasoning or {}).items() if k in ReasoningTrace.model_fields}) if reasoning else None,
    )

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO events (
                id, timestamp, destination, user_pseudo_id, page_title, trigger, char_count,
                decision, lt_rule, lt_action,
                severity, categories_json, classification_json, regulatory_json,
                prompt_excerpt, sanitized_excerpt, audit_message, override_applied,
                is_image, image_mime, image_ui_type, image_analysis_json,
                reasoning_json, embedding_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.timestamp.isoformat(),
                record.destination,
                record.user_pseudo_id,
                record.page_title,
                record.trigger,
                record.char_count,
                record.decision,
                record.lt_match.rule if record.lt_match else None,
                record.lt_match.action if record.lt_match else None,
                record.classification.severity,
                dumps(record.classification.categories),
                record.classification.model_dump_json(),
                dumps(record.classification.regulatory_concern),
                record.prompt_excerpt,
                record.sanitized_excerpt,
                record.audit_message,
                1 if record.override_applied else 0,
                1 if record.is_image else 0,
                record.image_mime,
                (record.image_analysis.ui_type if record.image_analysis else None),
                (record.image_analysis.model_dump_json() if record.image_analysis else None),
                (record.reasoning.model_dump_json() if record.reasoning else None),
                embedding_b64,
            ),
        )
        await db.commit()
    return record


# ─── POST /inspect ─────────────────────────────────────────────────────────────

@router.post("/inspect", response_model=InspectResponse)
async def inspect(req: InspectRequest) -> InspectResponse:
    # 1. Cheap pattern-based DPI via Lobster Trap on the raw prompt.
    lt = await inspect_prompt(req.prompt)

    # 2. If LT blocks outright, return immediately (no Gemini call).
    if lt.action == "DENY":
        classification = Classification.minimal_critical(
            f"Lobster Trap rule '{lt.matched_rule or 'unspecified'}' triggered."
        )
        audit_msg = block_message(lt)
        # Embed even blocks so the dashboard can cluster "who keeps trying"
        embedding = gemini.encode_vector(await gemini.embed(req.prompt))
        event = await _persist_event(
            req_context_dict=req.context.model_dump(),
            prompt_excerpt=_excerpt(req.prompt) or "",
            decision="block",
            lt=lt,
            classification=classification,
            sanitized=None,
            audit_message=audit_msg,
            embedding_b64=embedding,
        )
        return InspectResponse(
            decision="block",
            event_id=event.id,
            lt_match=lt.as_match(),
            classification=classification,
            sanitized_prompt=None,
            audit_message=audit_msg,
        )

    # 3. Semantic classification via Gemini (through LT).
    classification = await gemini.classify(req.prompt)

    # 4. THINKING-MODE ESCALATION — for ambiguous cases, ask Pro to deliberate.
    reasoning_payload: dict[str, Any] | None = None
    if _is_ambiguous(lt, classification):
        reasoning_payload = await gemini.think_about(req.prompt, classification)
        # If Pro confirms a higher severity, update the classification.
        new_sev = reasoning_payload.get("final_severity", classification.severity)
        if new_sev != classification.severity:
            classification = classification.model_copy(update={"severity": new_sev})
        # If Pro confirmed/added categories, prefer the merged list.
        merged = list(dict.fromkeys(
            (reasoning_payload.get("confirmed_categories") or [])
            + [c for c in classification.categories if c != "none"]
        ))
        if merged:
            classification = classification.model_copy(update={"categories": merged or ["none"]})

    # 5. Decide outcome.
    embedding = gemini.encode_vector(await gemini.embed(req.prompt))

    if classification.severity == "low" and lt.action == "ALLOW":
        event = await _persist_event(
            req_context_dict=req.context.model_dump(),
            prompt_excerpt=_excerpt(req.prompt) or "",
            decision="allow",
            lt=lt,
            classification=classification,
            sanitized=None,
            audit_message=None,
            reasoning=reasoning_payload,
            embedding_b64=embedding,
        )
        return InspectResponse(
            decision="allow",
            event_id=event.id,
            lt_match=None,
            classification=classification,
            sanitized_prompt=None,
            audit_message=None,
            reasoning=reasoning_payload,
        )

    # 6. Generate sanitized version (or use LT's redacted body if available).
    if lt.action == "REDACT" and lt.redacted_body:
        sanitized = lt.redacted_body
    else:
        sanitized = await gemini.sanitize(req.prompt, [c for c in classification.categories if c != "none"])

    audit_msg = _summarize_findings(classification)
    event = await _persist_event(
        req_context_dict=req.context.model_dump(),
        prompt_excerpt=_excerpt(req.prompt) or "",
        decision="redact",
        lt=lt,
        classification=classification,
        sanitized=sanitized,
        audit_message=audit_msg,
        reasoning=reasoning_payload,
        embedding_b64=embedding,
    )
    return InspectResponse(
        decision="redact",
        event_id=event.id,
        lt_match=lt.as_match() if lt.action != "ALLOW" else None,
        classification=classification,
        sanitized_prompt=sanitized,
        audit_message=audit_msg,
        reasoning=reasoning_payload,
    )


# ─── POST /inspect/image ───────────────────────────────────────────────────────

@router.post("/inspect/image", response_model=ImageInspectResponse)
async def inspect_image(req: ImageInspectRequest) -> ImageInspectResponse:
    """Inspect a pasted SCREENSHOT or image.

    Gemini Vision OCRs + classifies; the decision is:
      • block when the image contains credentials or extreme severity content
      • redact (with a TEXT ALTERNATIVE) when there's a safe rewrite
      • allow when benign (memes, public web, photographs of objects)

    We don't try to redact pixels — sanitization for images is a text-alternative
    generated by Pro that the employee can paste instead of the screenshot.
    """
    analysis = await gemini.classify_image(req.image_b64, req.image_mime)
    categories = analysis.get("categories", ["ui_screenshot"])
    severity = analysis.get("severity", "medium")
    findings = analysis.get("visible_sensitive_elements", [])
    explanation = analysis.get("explanation", "")
    regulatory = analysis.get("regulatory_concern", ["none"])

    classification = Classification(
        categories=[c for c in categories if c in {
            "source_code", "credentials", "customer_pii", "employee_pii", "financial_data",
            "strategic", "legal", "medical", "intellectual_property", "none",
        }] or ["intellectual_property"],
        severity=severity if severity in {"low", "medium", "high", "critical"} else "medium",
        specific_findings=[],
        explanation=explanation,
        suggest_sanitize=bool(analysis.get("suggest_text_alternative", False)),
        regulatory_concern=[r for r in regulatory if r in {"GDPR", "HIPAA", "SOX", "PCI-DSS", "trade_secret", "none"}] or ["none"],
    )

    # Decision logic — belt-and-braces. Belts: severity. Braces: structural cues.
    # Some Gemini Vision responses misclassify obviously-tabular screenshots as
    # "low" because the cell values look test-like (e.g., "test@email.com").
    # We override low→redact whenever the UI type itself signals high-risk
    # context (spreadsheet / CRM / financial / code editor / terminal / internal tool)
    # or when extracted text contains email/currency/credential patterns.
    ui_type = (analysis.get("ui_type") or "unknown").lower()
    high_risk_ui_types = {
        "spreadsheet", "crm_dashboard", "financial_dashboard",
        "code_editor", "terminal", "internal_tool",
    }
    extracted = (analysis.get("extracted_text_snippet") or "")
    import re as _re
    looks_like_pii = bool(_re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", extracted)) \
        or bool(_re.search(r"\$\s?[\d,]+", extracted)) \
        or bool(_re.search(r"\b\d{3}-\d{2}-\d{4}\b", extracted)) \
        or "AKIA" in extracted or "BEGIN PRIVATE KEY" in extracted

    decision: Decision
    sanitized_alt: str | None = None
    audit_msg: str | None = None

    if classification.severity == "critical":
        decision = "block"
        audit_msg = "Screenshot contains critical-severity data (likely credentials or extreme exposure). Cannot send to a public LLM."
    elif (
        classification.severity in {"medium", "high"}
        or findings
        or ui_type in high_risk_ui_types
        or looks_like_pii
    ):
        decision = "redact"
        sanitized_alt = await gemini.describe_image_safely(analysis)
        audit_msg = "Screenshot contains sensitive content. Paste the generated text alternative instead."
        # If we overrode a low severity to redact based on structural cues,
        # bump the classification so the dashboard shows the right severity.
        if classification.severity == "low":
            classification = classification.model_copy(update={"severity": "high"})
    else:
        decision = "allow"

    # Persist (note: image bytes are NOT stored — only the analysis + extracted snippet).
    excerpt = f"[image:{req.image_mime}] " + (analysis.get("extracted_text_snippet", "") or "")
    embedding = gemini.encode_vector(await gemini.embed(excerpt))
    event = await _persist_event(
        req_context_dict=req.context.model_dump(),
        prompt_excerpt=excerpt[:EXCERPT_LEN],
        decision=decision,
        lt=None,
        classification=classification,
        sanitized=sanitized_alt,
        audit_message=audit_msg,
        is_image=True,
        image_mime=req.image_mime,
        image_analysis=analysis,
        embedding_b64=embedding,
    )

    return ImageInspectResponse(
        decision=decision,
        event_id=event.id,
        classification=classification,
        image_analysis=analysis,
        sanitized_alternative=sanitized_alt,
        audit_message=audit_msg,
    )


# ─── POST /inspect/override ────────────────────────────────────────────────────

@router.post("/inspect/override")
async def mark_override(event_id: str) -> dict:
    async with get_db() as db:
        await db.execute("UPDATE events SET override_applied = 1 WHERE id = ?", (event_id,))
        await db.commit()
    return {"event_id": event_id, "override_applied": True}
