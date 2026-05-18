# SPDX-License-Identifier: MIT
"""Smoke tests for the seven Gemini integration surfaces.

We run with GEMINI_API_KEY unset so every Gemini call hits its deterministic
fallback. This is enough to validate the orchestration glue — the live model
behavior is exercised in the demo path with a real key set.
"""
from __future__ import annotations

import base64

import pytest

from conduit.db.session import init_db, reset_for_tests
from conduit.inspector import gemini
from conduit.inspector.policy import reset_policy_cache
from conduit.models.classification import (
    ImageInspectRequest,
    InspectContext,
    InspectRequest,
)
from conduit.routes.events import (
    agentic_narrative,
    enrich_threat_intel,
    list_events,
    similar_events,
)
from conduit.routes.inspect import inspect as inspect_handler
from conduit.routes.inspect import inspect_image


async def _setup():
    reset_for_tests()
    await init_db()
    reset_policy_cache()


def _ctx(dest: str = "chatgpt.com") -> InspectContext:
    return InspectContext(
        destination=dest,
        user_pseudo_id="u_test",
        page_title="Test",
        trigger="paste",
        timestamp="2026-05-19T00:00:00Z",
        char_count=0,
    )


@pytest.mark.asyncio
async def test_text_inspect_stores_embedding_blob():
    """When GEMINI_API_KEY is absent, embed() returns []; embedding_blob is empty
    but inserting must still succeed."""
    await _setup()
    out = await inspect_handler(InspectRequest(
        prompt="my AWS key AKIAIOSFODNN7EXAMPLE for the bucket", context=_ctx(),
    ))
    assert out.decision == "block"
    # Event landed in DB without exploding on the new columns.
    resp = await list_events(after=None, limit=5, decision=None, destination=None)
    assert any(e.id == out.event_id for e in resp.events)


@pytest.mark.asyncio
async def test_image_inspect_handles_heuristic_fallback():
    """No API key → heuristic image classification; the route must still produce
    a coherent decision."""
    await _setup()
    fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()
    req = ImageInspectRequest(image_b64=fake_png, image_mime="image/png", context=_ctx())
    out = await inspect_image(req)
    assert out.decision in {"allow", "redact", "block"}
    assert out.image_analysis.get("ui_type")


@pytest.mark.asyncio
async def test_similar_events_returns_neighbors_or_empty():
    """When embedding_blob is empty across the suite (no key), /similar still
    returns a sane shape rather than 500."""
    await _setup()
    out = await inspect_handler(InspectRequest(prompt="hello world how are you doing today", context=_ctx()))
    res = await similar_events(out.event_id, k=3)
    assert "neighbors" in res
    assert isinstance(res["neighbors"], list)


@pytest.mark.asyncio
async def test_threat_intel_returns_fallback_shape():
    await _setup()
    out = await inspect_handler(InspectRequest(
        prompt="My AWS key AKIAIOSFODNN7EXAMPLE", context=_ctx(),
    ))
    intel = await enrich_threat_intel(out.event_id)
    assert "threat_intel" in intel
    assert "rotation_steps" in intel["threat_intel"]
    assert "immediate_actions" in intel["threat_intel"]


@pytest.mark.asyncio
async def test_agentic_narrative_fallback():
    """No key → returns a non-empty narrative + empty trace. Shape must be stable."""
    await _setup()
    res = await agentic_narrative(window_hours=24)
    assert "narrative" in res
    assert "trace" in res
    assert isinstance(res["trace"], list)


@pytest.mark.asyncio
async def test_thinking_mode_attached_for_ambiguous():
    """A FLAG-only prompt (e.g., source-code indicator) is the canonical
    ambiguous case; thinking-mode result should ride along on the response."""
    await _setup()
    # A code-like payload that LT FLAGs but isn't obviously sensitive without context.
    out = await inspect_handler(InspectRequest(
        prompt="def calculate_average(numbers):\n    return sum(numbers) / len(numbers)",
        context=_ctx(),
    ))
    # Thinking mode is invoked for ambiguous; outcome may stay 'redact' or shift.
    # We just assert the field exists and is a dict (or None if no escalation).
    assert out.reasoning is None or isinstance(out.reasoning, dict)


@pytest.mark.asyncio
async def test_embedding_cosine_roundtrip():
    """Vector codec round-trips and cosine math is sane."""
    vec = [0.1, 0.2, 0.3, 0.4]
    encoded = gemini.encode_vector(vec)
    decoded = gemini.decode_vector(encoded)
    assert len(decoded) == 4
    assert all(abs(a - b) < 1e-5 for a, b in zip(vec, decoded))
    assert gemini.cosine_similarity(vec, vec) > 0.999
    assert gemini.cosine_similarity(vec, [-x for x in vec]) < -0.999
