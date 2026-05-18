# SPDX-License-Identifier: MIT
"""Gemini classification + sanitization, ALWAYS via Lobster Trap.

CRITICAL invariant:
  the OpenAI client's base_url is the LT proxy URL, never Gemini's direct endpoint.
  Enforced by tests/test_no_direct_gemini.py — any source file under conduit/ that
  references the direct Gemini hostname fails the build.

This module covers all seven Gemini surfaces Conduit uses:
  1. classify(text)              — gemini-2.5-flash, structured JSON
  2. sanitize(text, categories)  — gemini-2.5-pro
  3. narrate(events_json)        — gemini-2.5-pro, daily CISO summary
  4. classify_image(image, mime) — gemini-2.5-flash with vision input
  5. describe_image_safely(...)  — gemini-2.5-pro, generates a text alternative
  6. think_about(prompt, first_pass) — gemini-2.5-pro thinking mode for ambiguous cases
  7. enrich_threat_intel(creds)  — gemini-2.5-pro + google_search grounding tool
  8. agentic_narrate(...)        — function-calling: Gemini calls back into Conduit MCP
  9. embed(text)                 — gemini-embedding-001 for similarity clustering
"""
from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI

from ..config import settings
from ..models.classification import Classification
from ..prompts import (
    AGENTIC_NARRATIVE_SYSTEM_PROMPT,
    AUDIT_NARRATIVE_SYSTEM_PROMPT,
    CLASSIFICATION_SYSTEM_PROMPT,
    IMAGE_CLASSIFICATION_SYSTEM_PROMPT,
    IMAGE_TEXT_ALTERNATIVE_SYSTEM_PROMPT,
    SANITIZATION_SYSTEM_PROMPT,
    THINKING_ESCALATION_SYSTEM_PROMPT,
    THREAT_INTEL_SYSTEM_PROMPT,
)

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.LT_GEMINI_BASE_URL,
        api_key=settings.GEMINI_API_KEY or "dev-no-key",
    )


# ─── 1. Text classification (gemini-2.5-flash, JSON mode) ─────────────────────

def _heuristic_classification(prompt: str) -> Classification:
    from .policy import evaluate

    lt = evaluate(prompt)
    if lt.action == "DENY":
        return Classification(
            categories=["credentials"],
            severity="critical",
            specific_findings=[],
            explanation=f"Hard-block by policy rule '{lt.matched_rule}'.",
            suggest_sanitize=False,
            regulatory_concern=["none"],
        )
    if lt.action == "REDACT":
        cats: list = list(lt.detected_categories) or ["customer_pii"]
        return Classification(
            categories=cats,  # type: ignore[arg-type]
            severity="high",
            specific_findings=[],
            explanation=f"PII pattern matched by '{lt.matched_rule}'.",
            suggest_sanitize=True,
            regulatory_concern=["GDPR"] if any(c.endswith("pii") for c in cats) else ["none"],
        )
    if lt.action == "FLAG":
        cats = list(lt.detected_categories) or ["intellectual_property"]
        return Classification(
            categories=cats,  # type: ignore[arg-type]
            severity="medium",
            specific_findings=[],
            explanation=f"Semantic review needed (rule '{lt.matched_rule}').",
            suggest_sanitize=True,
            regulatory_concern=["trade_secret"] if "source_code" in cats else ["none"],
        )
    return Classification.benign()


async def classify(prompt: str) -> Classification:
    if not settings.GEMINI_API_KEY:
        return _heuristic_classification(prompt)
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_CLASSIFY,
            messages=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = resp.choices[0].message.content or "{}"
        return Classification.model_validate_json(content)
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini classify failed (%s); falling back to heuristic", exc)
        return _heuristic_classification(prompt)


# ─── 2. Sanitization (gemini-2.5-pro) ─────────────────────────────────────────

def _local_sanitize(prompt: str, categories: list[str]) -> str:
    from .policy import evaluate

    decision = evaluate(prompt)
    if decision.action == "REDACT" and decision.redacted_body:
        return decision.redacted_body
    return prompt


async def sanitize(prompt: str, categories: list[str]) -> str:
    if not settings.GEMINI_API_KEY:
        return _local_sanitize(prompt, categories)
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_SANITIZE,
            messages=[
                {"role": "system", "content": SANITIZATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"categories": categories, "prompt": prompt})},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini sanitize failed (%s); falling back to local pattern sanitizer", exc)
        return _local_sanitize(prompt, categories)


# ─── 3. Daily narrative (gemini-2.5-pro) ──────────────────────────────────────

async def narrate(events_json: str) -> str:
    if not settings.GEMINI_API_KEY:
        return (
            "Daily narrative generation requires a configured GEMINI_API_KEY. "
            "When configured, Conduit summarizes categories, destinations, "
            "critical-severity blocks, and one recommended next action here."
        )
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_NARRATIVE,
            messages=[
                {"role": "system", "content": AUDIT_NARRATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": events_json},
            ],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini narrate failed: %s", exc)
        return "Narrative unavailable — Gemini proxy returned an error."


# ─── 4. Multimodal image classification (gemini-2.5-flash + vision) ──────────

def _heuristic_image_classification(extracted_hint: str = "") -> dict[str, Any]:
    """Used when Gemini Vision is unavailable. Conservative — assumes screenshots
    of business UIs are sensitive until proven otherwise."""
    return {
        "categories": ["ui_screenshot", "intellectual_property"],
        "severity": "medium",
        "ui_type": "generic_screenshot",
        "visible_sensitive_elements": [],
        "extracted_text_snippet": extracted_hint[:200],
        "explanation": "Image inspection unavailable — defaulting to flag for review.",
        "suggest_text_alternative": True,
        "regulatory_concern": ["none"],
    }


async def classify_image(image_b64: str, image_mime: str = "image/png") -> dict[str, Any]:
    """Run Gemini Vision on a base64-encoded screenshot. Returns the same shape
    described in IMAGE_CLASSIFICATION_SYSTEM_PROMPT plus a raw dict for the route
    handler to project into the audit record.
    """
    if not settings.GEMINI_API_KEY:
        return _heuristic_image_classification()
    try:
        data_url = f"data:{image_mime};base64,{image_b64}"
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_CLASSIFY,
            messages=[
                {"role": "system", "content": IMAGE_CLASSIFICATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Classify this image for corporate-data sensitivity."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini classify_image failed: %s", exc)
        return _heuristic_image_classification()


async def describe_image_safely(image_analysis: dict[str, Any]) -> str:
    """Generate a text alternative the employee can paste instead of the screenshot.

    Uses gemini-2.5-pro because the rewrite needs to infer the user's likely
    question from the visible UI — a reasoning task Flash sometimes flubs.
    """
    fallback = (
        "I have a screenshot of " + image_analysis.get("ui_type", "an internal application")
        + " showing sensitive corporate data. Instead of pasting it, please describe what you'd like to do "
          "with the data and I'll explain how to do it without sharing actual customer/employee/financial records."
    )
    if not settings.GEMINI_API_KEY:
        return fallback
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_SANITIZE,
            messages=[
                {"role": "system", "content": IMAGE_TEXT_ALTERNATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(image_analysis)},
            ],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or fallback).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini describe_image_safely failed: %s", exc)
        return fallback


# ─── 5. Thinking-mode escalation (gemini-2.5-pro reasoning) ───────────────────

async def think_about(prompt: str, first_pass: Classification) -> dict[str, Any]:
    """Ask Gemini 2.5 Pro to deliberate on an ambiguous classification.

    We pass `reasoning_effort='medium'` via the extra body params — the OpenAI-
    compatible Gemini endpoint accepts `thinking_config` for the Pro models.
    Falls back to the first-pass result if reasoning is unavailable.
    """
    payload = {
        "prompt": prompt[:2000],
        "first_pass": first_pass.model_dump(),
    }
    fallback = {
        "final_severity": first_pass.severity,
        "confirmed_categories": [c for c in first_pass.categories if c != "none"] or ["none"],
        "reasoning_summary": "Thinking mode unavailable — using first-pass classification as-is.",
        "decision_change": "confirmed",
        "regulatory_concern": first_pass.regulatory_concern,
    }
    if not settings.GEMINI_API_KEY:
        return fallback
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_SANITIZE,  # Pro
            messages=[
                {"role": "system", "content": THINKING_ESCALATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            extra_body={
                "extra_body": {
                    "google": {"thinking_config": {"thinking_budget": 4096, "include_thoughts": True}}
                }
            },
        )
        content = resp.choices[0].message.content or "{}"
        out = json.loads(content)
        out.setdefault("decision_change", "confirmed")
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini thinking-mode call failed: %s", exc)
        return fallback


# ─── 6. Threat-intel enrichment (gemini-2.5-pro + Google Search) ──────────────

async def enrich_threat_intel(credential_type: str, lt_rule: str | None) -> dict[str, Any]:
    """Use Gemini's Google Search grounding tool to fetch current threat-intel for
    a leaked credential type. Returns rotation steps, recent breaches, threat-actor
    notes, and an immediate-action checklist.

    The OpenAI-compatible Gemini endpoint exposes the google_search tool via the
    `tools` parameter; the response includes `groundingMetadata` with citations.
    """
    user_msg = (
        f"An employee just leaked (or tried to leak) a credential of type: {credential_type!r}. "
        f"Lobster Trap matched rule: {lt_rule or 'unknown'}. "
        "Produce the threat-intel brief described in your instructions, using Google Search to ground every claim."
    )
    fallback = {
        "rotation_steps": (
            "1. Locate the credential in your secrets manager.\n"
            "2. Revoke the leaked credential at the issuing system.\n"
            "3. Issue a replacement and deploy to all dependent services.\n"
            "4. Audit access logs for unauthorized use of the leaked credential."
        ),
        "recent_breaches": [],
        "threat_actor_notes": "Threat-intel grounding requires GEMINI_API_KEY; configure it to enable live search-grounded enrichment.",
        "immediate_actions": [
            "Rotate the credential immediately.",
            "Audit recent access logs for the affected resource.",
            "Notify the credential owner and CISO.",
        ],
        "sources": [],
    }
    if not settings.GEMINI_API_KEY:
        return fallback
    try:
        resp = await _client().chat.completions.create(
            model=settings.GEMINI_MODEL_NARRATIVE,  # Pro
            messages=[
                {"role": "system", "content": THREAT_INTEL_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            extra_body={"tools": [{"googleSearch": {}}]},
        )
        text = resp.choices[0].message.content or "{}"
        # Strip code fences if Gemini wrapped JSON in them despite the instructions.
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        out = json.loads(text)
        # Surface grounding citations if present.
        grounding = getattr(resp.choices[0].message, "grounding_metadata", None)
        if grounding:
            out["_grounding"] = str(grounding)[:2000]
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini threat-intel grounding failed: %s", exc)
        return fallback


# ─── 7. Agentic narrative via function calling ────────────────────────────────

AGENTIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Get aggregate counts of audit events by decision/severity/category/destination.",
            "parameters": {
                "type": "object",
                "properties": {"window_hours": {"type": "integer", "default": 24}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_events",
            "description": "List recent audit events, optionally filtered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["allow", "redact", "block"]},
                    "limit": {"type": "integer", "default": 10},
                    "hours": {"type": "integer", "default": 24},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_detail",
            "description": "Get the full detail of a specific audit event by id.",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
            },
        },
    },
]


async def agentic_narrate(tool_runner) -> dict[str, Any]:
    """Function-calling loop: Gemini investigates the audit log via Conduit's own
    tools, then writes the daily brief. Returns the brief plus the trace of tool
    calls so the dashboard can show *how* the agent reached its conclusion.

    `tool_runner` is an async callable: tool_runner(name, args_dict) -> dict.
    """
    trace: list[dict[str, Any]] = []
    fallback = {
        "narrative": "Agentic narrative requires GEMINI_API_KEY; configure it to enable function-calling investigation.",
        "trace": trace,
    }
    if not settings.GEMINI_API_KEY:
        return fallback

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENTIC_NARRATIVE_SYSTEM_PROMPT},
        {"role": "user", "content": "Write today's CISO morning brief. Investigate first."},
    ]
    try:
        for hop in range(6):  # cap the loop
            resp = await _client().chat.completions.create(
                model=settings.GEMINI_MODEL_NARRATIVE,
                messages=messages,
                tools=AGENTIC_TOOLS,
                temperature=0.2,
            )
            choice = resp.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None) or []
            if not tool_calls:
                final_text = (choice.content or "").strip()
                return {"narrative": final_text, "trace": trace, "hops": hop + 1}

            messages.append({"role": "assistant", "tool_calls": [tc.model_dump() for tc in tool_calls], "content": choice.content or ""})
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await tool_runner(name, args)
                trace.append({"tool": name, "args": args, "result_preview": str(result)[:400]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)[:4000],
                })
        # If we exceed the hop budget, return what we have.
        return {"narrative": "Agent exceeded investigation budget without converging.", "trace": trace}
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini agentic narrate failed: %s", exc)
        return {"narrative": f"Agentic narrative failed: {exc}", "trace": trace}


# ─── 8. Embeddings (gemini-embedding-001) ─────────────────────────────────────

async def embed(text: str) -> list[float]:
    """Embed a string with gemini-embedding-001. Returns an empty list if unavailable;
    callers must handle [] as "skip similarity check"."""
    if not settings.GEMINI_API_KEY:
        return []
    try:
        resp = await _client().embeddings.create(
            model="gemini-embedding-001",
            input=text[:8000],  # generous truncation; embed model handles 8k+
        )
        return list(resp.data[0].embedding)
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini embed failed: %s", exc)
        return []


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain cosine — fast enough for the hackathon-scale audit log (<10k events).
    For production, swap in pgvector or a proper vector store."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na ** 0.5 * nb ** 0.5)


def encode_vector(vec: list[float]) -> str:
    """Compact base64-encoded float32 representation for SQLite storage."""
    import struct

    if not vec:
        return ""
    return base64.b64encode(struct.pack(f"{len(vec)}f", *vec)).decode("ascii")


def decode_vector(blob: str | None) -> list[float]:
    import struct

    if not blob:
        return []
    raw = base64.b64decode(blob)
    n = len(raw) // 4
    return list(struct.unpack(f"{n}f", raw))
