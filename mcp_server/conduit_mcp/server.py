# SPDX-License-Identifier: MIT
"""Conduit MCP server.

Exposes Conduit's shadow-AI governance surface to MCP-compatible AI agents:
  • Tools — actions and read queries (inspect, audit search, stats, narrative, policy)
  • Resources — read-only artifacts (live policy.yaml, recent events, test results)
  • Prompts — pre-baked agent prompt templates (CISO audit, policy gap review)

Why this matters for the hackathon:
  Lobster Trap is Conduit's inspection engine for human paste events.
  This MCP server lets an *agent* (Claude Desktop, an internal copilot, a Slack bot)
  query the same audit trail and run the same inspection — bringing Conduit's
  governance surface into agentic workflows. Track 1's brief asks for "audit trails
  a regulator could read"; MCP makes that audit trail conversable.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from .client import backend, pretty
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s conduit-mcp: %(message)s",
    stream=sys.stderr,  # stdio transport: must keep stdout clean for JSON-RPC
)
log = logging.getLogger(__name__)

mcp = FastMCP(
    name="conduit",
    instructions=(
        "Conduit governs shadow-AI data egress. Use these tools to: "
        "(1) audit prompts employees have sent (or tried to send) to public LLMs; "
        "(2) inspect a new prompt against the corporate policy + Lobster Trap + Gemini; "
        "(3) read the active policy rules; (4) generate a CISO daily narrative. "
        "When investigating an incident, start with conduit_stats to scope, then "
        "conduit_list_events to find the offending events, then conduit_get_event for full detail."
    ),
)


# ─── Tools ──────────────────────────────────────────────────────────────

@mcp.tool()
async def conduit_inspect(
    prompt: str,
    destination: str = "manual",
    trigger: str = "manual",
    ctx: Context | None = None,
) -> str:
    """Inspect a prompt against the corporate egress policy.

    Runs the same end-to-end pipeline used by the browser extension:
    Lobster Trap pattern DPI → Gemini 2.5 Flash classification → Gemini 2.5 Pro
    sanitization. Returns a decision ('allow' | 'redact' | 'block'), the matched
    Lobster Trap rule, the Gemini classification, and a sanitized version when
    redaction is appropriate.

    Use this from an agent flow to:
      • Validate a draft before forwarding to a public LLM.
      • Pre-check an outbound message in a Slack bot or email assistant.
      • Build a 'safe-paste' helper for analysts working with customer data.

    Args:
        prompt: The text to inspect.
        destination: Optional destination tag for the audit log (e.g. 'chatgpt.com').
        trigger: Optional trigger label ('manual', 'agent', 'paste').

    Returns:
        Pretty JSON: { decision, event_id, lt_match, classification, sanitized_prompt, audit_message }
    """
    if ctx is not None:
        await ctx.info(f"Inspecting {len(prompt)} chars headed to {destination!r}")
    resp = await backend.inspect(prompt, destination=destination, trigger=trigger)
    return pretty(resp)


@mcp.tool()
async def conduit_list_events(
    limit: int = 25,
    decision: str | None = None,
    destination: str | None = None,
    since: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Search the audit log.

    Returns a list of recent events, newest first. Each event includes the
    Conduit decision, the Lobster Trap rule that matched, the Gemini
    classification (categories + severity + regulatory_concern), and a 240-char
    prompt excerpt (full body never leaves the backend).

    Filters compose: e.g. `decision='block', destination='chatgpt.com'` to find
    every credential-leak attempt aimed at ChatGPT.

    Args:
        limit: Max events to return (1–500).
        decision: Optional filter — 'allow', 'redact', or 'block'.
        destination: Optional hostname filter — 'chatgpt.com', 'claude.ai', ...
        since: ISO-8601 timestamp; events strictly after this are returned.

    Returns:
        Pretty JSON: { events: [...], next_cursor: <iso> }
    """
    if decision and decision not in ("allow", "redact", "block"):
        return pretty({"error": "decision must be one of: allow, redact, block"})
    if ctx is not None:
        await ctx.info(f"Listing up to {limit} events (decision={decision}, dest={destination})")
    resp = await backend.list_events(limit=limit, after=since, decision=decision, destination=destination)
    return pretty(resp)


@mcp.tool()
async def conduit_get_event(event_id: str) -> str:
    """Fetch a single audit event in full detail.

    Args:
        event_id: The 'evt_…' id returned from conduit_list_events or conduit_inspect.

    Returns:
        Pretty JSON with the full event record (LT match, classification, both excerpts, overrides).
    """
    resp = await backend.get_event(event_id)
    return pretty(resp)


@mcp.tool()
async def conduit_stats(window_hours: int = 24, ctx: Context | None = None) -> str:
    """Aggregate stats over a rolling window.

    Returns counts by decision (allow/redact/block), by severity, by Gemini
    category, and by destination domain. Use as the entry point for "is anything
    on fire?" investigations.

    Args:
        window_hours: Window in hours (1 – 720). Default 24.
    """
    if ctx is not None:
        await ctx.info(f"Fetching stats for last {window_hours}h")
    resp = await backend.stats(window_hours=window_hours)
    return pretty(resp)


@mcp.tool()
async def conduit_narrate(window_hours: int = 24, ctx: Context | None = None) -> str:
    """Generate a CISO daily narrative paragraph.

    Calls Gemini 2.5 Pro (via Lobster Trap) over the last `window_hours` of events
    and returns a regulator-readable summary: top categories, top destinations,
    critical-severity blocks, one recommended next action.

    Args:
        window_hours: Window for the narrative. Default 24 (the canonical CISO daily).
    """
    if ctx is not None:
        await ctx.info(f"Generating narrative for last {window_hours}h via Gemini 2.5 Pro")
    resp = await backend.narrative(window_hours=window_hours)
    return pretty(resp)


@mcp.tool()
async def conduit_policy_rules() -> str:
    """List the active Lobster Trap policy rules.

    Each rule has a name, action (ALLOW/REDACT/DENY/FLAG), priority, and human
    description. Use to answer "what categories does Conduit catch?" or to
    look up which rule matched a given event.
    """
    resp = await backend.policy_rules()
    return pretty(resp)


@mcp.tool()
async def conduit_mark_override(event_id: str) -> str:
    """Mark an audit event as 'override applied' — the user chose to send the original
    prompt despite Conduit's redact recommendation.

    Only call this for genuine overrides. The dashboard surfaces overrides
    distinctly so the CISO can investigate.
    """
    resp = await backend.mark_override(event_id)
    return pretty(resp)


@mcp.tool()
async def conduit_health() -> str:
    """Lightweight health probe — confirms Conduit's backend, Lobster Trap proxy
    URL, and Gemini configuration are reachable from this MCP server."""
    resp = await backend.health()
    return pretty(resp)


# ─── Gemini-heavy tools (multimodal, search-grounded, agentic, similarity) ─────

@mcp.tool()
async def conduit_inspect_image(
    image_b64: str,
    image_mime: str = "image/png",
    destination: str = "manual",
    ctx: Context | None = None,
) -> str:
    """Inspect a SCREENSHOT or image for sensitive corporate data.

    Uses Gemini Vision (gemini-2.5-flash with image input) to OCR + classify
    the image's UI type + identify visible sensitive elements. If the image
    contains sensitive content, Gemini 2.5 Pro generates a TEXT ALTERNATIVE
    the user can paste instead of the screenshot.

    Use this when an agent receives a screenshot in a Slack/Teams thread that
    a user wants to forward to a public LLM — call this first, paste the
    sanitized_alternative instead.

    Args:
        image_b64: Base64-encoded image bytes (no data: prefix).
        image_mime: MIME type — typical: image/png, image/jpeg.
        destination: Optional tag for the audit log.
    """
    if ctx is not None:
        await ctx.info(f"Inspecting image ({image_mime}, {len(image_b64)} b64 chars)")
    resp = await backend.inspect_image(image_b64, image_mime=image_mime, destination=destination)
    return pretty(resp)


@mcp.tool()
async def conduit_similar_events(event_id: str, k: int = 5) -> str:
    """Find the K events most similar to a given event, by Gemini-embedding cosine.

    Use for incident pattern-matching: 'has this exfil pattern appeared before?'
    or 'is this user a repeat offender?'. Powered by gemini-embedding-001 over
    the prompt excerpts.

    Args:
        event_id: The event to find neighbors for.
        k: How many neighbors to return (1–25).
    """
    resp = await backend.similar_events(event_id, k=k)
    return pretty(resp)


@mcp.tool()
async def conduit_threat_intel(event_id: str, ctx: Context | None = None) -> str:
    """Generate live threat intelligence for an event involving a leaked credential.

    Uses Gemini 2.5 Pro with the google_search grounding tool. Returns:
      • rotation_steps — how to rotate this credential type (linked to official docs)
      • recent_breaches — recent public incidents involving this credential class
      • threat_actor_notes — who targets this credential type
      • immediate_actions — checklist for the next 30 minutes
      • sources — URLs the assertions are grounded against

    Use after conduit_get_event flagged a credential-class block, to draft the
    incident-response handoff to the credential owner.

    Args:
        event_id: The audit event id from conduit_list_events or conduit_inspect.
    """
    if ctx is not None:
        await ctx.info(f"Enriching {event_id} with Gemini search-grounded threat intel")
    resp = await backend.threat_intel(event_id)
    return pretty(resp)


@mcp.tool()
async def conduit_agentic_narrative(window_hours: int = 24, ctx: Context | None = None) -> str:
    """Generate a CISO morning brief where Gemini investigates the audit log
    using function calling before writing.

    Internally Gemini calls back into Conduit's own audit endpoints (get_stats,
    list_recent_events, get_event_detail) to ground its narrative. The response
    includes the brief AND the trace of tool calls so the CISO can see *how* the
    agent reached its conclusion — explainability built in.

    Args:
        window_hours: Time window for the brief. Default 24.
    """
    if ctx is not None:
        await ctx.info("Running agentic narrative via Gemini function-calling")
    resp = await backend.agentic_narrative(window_hours=window_hours)
    return pretty(resp)


# ─── Resources ──────────────────────────────────────────────────────────

@mcp.resource("conduit://policy/yaml", mime_type="application/yaml")
async def policy_yaml_resource() -> str:
    """The active Lobster Trap policy YAML as text. Same file mounted into the
    LT proxy at runtime; readable by agents that need rule semantics, not just
    rule names."""
    candidates = [
        Path("/policies/policy.yaml"),
        Path(__file__).resolve().parents[2] / "lobster_trap" / "policy.yaml",
        Path("./lobster_trap/policy.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "# policy.yaml not found in standard locations"


@mcp.resource("conduit://events/recent", mime_type="application/json")
async def recent_events_resource() -> str:
    """The 50 most recent audit events as JSON. Snapshot at read-time; refresh
    by re-reading the resource. For interactive querying use the
    conduit_list_events tool with filters."""
    try:
        data = await backend.list_events(limit=50)
        return pretty(data)
    except Exception as exc:  # noqa: BLE001
        return pretty({"error": f"backend unreachable: {exc}"})


@mcp.resource("conduit://stats/today", mime_type="application/json")
async def stats_today_resource() -> str:
    """24-hour rolling stats snapshot. Top-of-funnel for CISO morning review."""
    try:
        data = await backend.stats(window_hours=24)
        return pretty(data)
    except Exception as exc:  # noqa: BLE001
        return pretty({"error": f"backend unreachable: {exc}"})


@mcp.resource("conduit://tests/results", mime_type="text/plain")
async def test_results_resource() -> str:
    """Most recent adversarial+benign suite results. Shows the 30/10 grid judges
    look at in the dashboard."""
    candidates = [
        Path(__file__).resolve().parents[2] / "backend" / "tests" / "results.txt",
        Path("/data/results.txt"),
        Path("./backend/tests/results.txt"),
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "results.txt not found — run `pytest` in backend/ first."


# ─── Prompts ────────────────────────────────────────────────────────────

@mcp.prompt(title="Daily shadow-AI audit")
def daily_audit_prompt(hours: int = 24) -> list[dict[str, Any]]:
    """Pre-baked prompt for an agent that conducts the morning shadow-AI review."""
    return [
        {
            "role": "user",
            "content": (
                f"You are an AI security analyst. Using the conduit MCP tools, audit the last {hours} "
                "hours of corporate AI usage. Steps:\n"
                "1. Call conduit_stats to get the totals.\n"
                "2. If any 'critical' severity events exist, call conduit_list_events with decision='block' "
                "to surface them, then conduit_get_event on each.\n"
                "3. Call conduit_narrate to retrieve the Gemini-generated CISO summary.\n"
                "4. Write a short report (under 200 words) summarizing what you found, what's actionable, "
                "and which one alert (if any) the CISO should look at first."
            ),
        }
    ]


@mcp.prompt(title="Policy gap review")
def policy_gap_review_prompt() -> list[dict[str, Any]]:
    """Pre-baked prompt for an agent that audits the policy itself."""
    return [
        {
            "role": "user",
            "content": (
                "You are a corporate AI-governance auditor. Read the conduit://policy/yaml resource "
                "and the conduit://events/recent resource. Find one gap: a class of sensitive data the "
                "policy doesn't currently catch but the recent events suggest is leaking. Propose a single "
                "new rule (with name, action, regex, priority) that would close that gap. Justify the "
                "false-positive risk in one sentence."
            ),
        }
    ]


# ─── Entrypoint ─────────────────────────────────────────────────────────

def main() -> None:
    """Console entry point — `conduit-mcp` after `pip install`."""
    transport = settings.MCP_TRANSPORT.lower()
    log.info("Starting conduit-mcp via %s transport; backend=%s", transport, settings.CONDUIT_BACKEND_URL)
    if transport == "http" or transport == "streamable-http":
        # Streamable HTTP for remote agents (e.g. internal copilot in another VPC).
        mcp.settings.host = settings.MCP_HTTP_HOST
        mcp.settings.port = settings.MCP_HTTP_PORT
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.settings.host = settings.MCP_HTTP_HOST
        mcp.settings.port = settings.MCP_HTTP_PORT
        mcp.run(transport="sse")
    else:
        # Default: stdio — Claude Desktop, mcp-cli, any local MCP client.
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
