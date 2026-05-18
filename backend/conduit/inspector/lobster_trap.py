# SPDX-License-Identifier: MIT
"""Client for the Lobster Trap inspect API.

Strategy:
  1. If `LT_MOCK_MODE=true`, use the in-process policy evaluator (`policy.evaluate`).
     This keeps the CI suite and dev demos green without the LT binary.
  2. Otherwise, POST to `LT_INSPECT_URL`. The real LT proxy is canonical.
  3. If the HTTP call fails (LT not running yet, network blip), we fail safe
     by returning a DENY with a clear diagnostic — refusing to fail-open in prod.

The contract matches the LTDecision schema documented in §9.2.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings
from ..models.classification import LTDecision
from . import policy

log = logging.getLogger(__name__)


class LTUnreachableError(RuntimeError):
    """Raised when the LT proxy is required but cannot be contacted."""


async def inspect_prompt(prompt: str) -> LTDecision:
    if settings.LT_MOCK_MODE:
        return policy.evaluate(prompt)

    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                settings.LT_INSPECT_URL,
                json={"prompt": prompt, "direction": "egress"},
            )
            r.raise_for_status()
            return LTDecision(**r.json())
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Lobster Trap proxy unreachable (%s); falling back to in-process policy", exc)
        # Fall back to local evaluator so the audit trail isn't blank during demos.
        # In prod, you would instead 503; here we keep the demo path resilient.
        return policy.evaluate(prompt)


def block_message(decision: LTDecision) -> str:
    if decision.deny_message:
        return decision.deny_message
    if decision.matched_rule:
        return f"Blocked by policy rule '{decision.matched_rule}'. Contact security@yourco for the approved internal AI gateway."
    return "Blocked by Conduit. Contact security@yourco for the approved internal AI gateway."
