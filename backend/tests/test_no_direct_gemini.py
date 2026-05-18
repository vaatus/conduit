# SPDX-License-Identifier: MIT
"""Architectural invariant: backend never talks to Gemini directly.

Every Gemini call must traverse Lobster Trap. If a file under conduit/ ever
references the direct endpoint, the LT story collapses and so does the Veea
prize case. This test fails the build if that ever happens.
"""
from __future__ import annotations

import pathlib

FORBIDDEN = "generativelanguage.googleapis.com"


def test_no_direct_gemini_calls():
    backend_dir = pathlib.Path(__file__).parent.parent / "conduit"
    hits: list[str] = []
    for py in backend_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if FORBIDDEN in text:
            hits.append(str(py.relative_to(backend_dir)))
    assert not hits, (
        "Backend source must call Gemini through Lobster Trap only.\n"
        f"Direct Gemini reference found in: {hits}\n"
        "Move the call into inspector/gemini.py and route via settings.LT_GEMINI_BASE_URL."
    )


def test_lt_gemini_base_url_points_at_lobster_trap():
    from conduit.config import settings

    assert "generativelanguage.googleapis.com" not in settings.LT_GEMINI_BASE_URL, (
        "LT_GEMINI_BASE_URL must point at the LT proxy, never at Gemini directly."
    )
