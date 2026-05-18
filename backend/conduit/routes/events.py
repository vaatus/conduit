# SPDX-License-Identifier: MIT
"""GET /events, GET /events/{id}, GET /events/{id}/similar,
   POST /events/{id}/enrich/threat-intel, GET /stats, POST /stats/narrative,
   POST /stats/narrative/agentic, GET /policy/rules.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..db.session import get_db, loads
from ..inspector import gemini
from ..inspector.policy import rule_summary
from ..models.classification import Classification, LTMatch
from ..models.event import EventListResponse, EventRecord, ImageAnalysis, ReasoningTrace, StatsSummary

router = APIRouter()


def _row_to_event(row) -> EventRecord:
    classification_data = loads(row["classification_json"], {}) or {}
    classification = Classification.model_validate(classification_data) if classification_data else Classification.benign()
    lt_match = None
    if row["lt_action"]:
        lt_match = LTMatch(rule=row["lt_rule"], action=row["lt_action"])

    image_analysis = None
    try:
        img_json = row["image_analysis_json"]
    except (IndexError, KeyError):
        img_json = None
    if img_json:
        data = loads(img_json, {}) or {}
        image_analysis = ImageAnalysis(
            ui_type=data.get("ui_type", "unknown"),
            visible_sensitive_elements=data.get("visible_sensitive_elements", []) or [],
            extracted_text_snippet=data.get("extracted_text_snippet", "") or "",
            suggest_text_alternative=bool(data.get("suggest_text_alternative", False)),
        )

    reasoning = None
    try:
        r_json = row["reasoning_json"]
    except (IndexError, KeyError):
        r_json = None
    if r_json:
        rdata = loads(r_json, {}) or {}
        reasoning = ReasoningTrace(
            final_severity=rdata.get("final_severity", "low"),
            confirmed_categories=rdata.get("confirmed_categories", []) or [],
            reasoning_summary=rdata.get("reasoning_summary", ""),
            decision_change=rdata.get("decision_change", "confirmed"),
        )

    try:
        is_image = bool(row["is_image"])
        image_mime = row["image_mime"]
    except (IndexError, KeyError):
        is_image = False
        image_mime = None

    return EventRecord(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        destination=row["destination"],
        user_pseudo_id=row["user_pseudo_id"],
        page_title=row["page_title"],
        trigger=row["trigger"],
        char_count=row["char_count"] or 0,
        decision=row["decision"],
        lt_match=lt_match,
        classification=classification,
        prompt_excerpt=row["prompt_excerpt"] or "",
        sanitized_excerpt=row["sanitized_excerpt"],
        override_applied=bool(row["override_applied"]),
        audit_message=row["audit_message"],
        is_image=is_image,
        image_mime=image_mime,
        image_analysis=image_analysis,
        reasoning=reasoning,
    )


@router.get("/events", response_model=EventListResponse)
async def list_events(
    after: str | None = Query(None, description="Return events strictly after this ISO timestamp"),
    limit: int = Query(50, ge=1, le=500),
    decision: str | None = Query(None, pattern="^(allow|redact|block)$"),
    destination: str | None = None,
) -> EventListResponse:
    where: list[str] = []
    params: list = []
    if after:
        where.append("timestamp > ?")
        params.append(after)
    if decision:
        where.append("decision = ?")
        params.append(decision)
    if destination:
        where.append("destination = ?")
        params.append(destination)
    sql = "SELECT * FROM events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    async with get_db() as db:
        rows = await (await db.execute(sql, tuple(params))).fetchall()
    events = [_row_to_event(r) for r in rows]
    next_cursor = events[0].timestamp.isoformat() if events else None
    return EventListResponse(events=events, next_cursor=next_cursor)


@router.get("/events/{event_id}", response_model=EventRecord)
async def get_event(event_id: str) -> EventRecord:
    async with get_db() as db:
        row = await (await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    return _row_to_event(row)


# ─── Embedding-based similarity (Gemini embeddings) ───────────────────────────

@router.get("/events/{event_id}/similar")
async def similar_events(event_id: str, k: int = Query(5, ge=1, le=25)) -> dict:
    """Find the K most similar prior events by cosine distance over Gemini embeddings.

    Use case: when an incident is being investigated, surface "other times this
    pattern appeared". Lets a CISO see clusters — e.g., the same user pasting the
    same source class repeatedly, or the same exfil pattern across three users.
    """
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT id, embedding_blob, prompt_excerpt, destination FROM events WHERE id = ?",
            (event_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="event not found")
        target_vec = gemini.decode_vector(row["embedding_blob"])
        if not target_vec:
            return {"event_id": event_id, "neighbors": [], "note": "Embedding not stored for this event."}

        cursor = await db.execute(
            "SELECT id, timestamp, destination, decision, severity, categories_json, prompt_excerpt, embedding_blob "
            "FROM events WHERE id != ? AND embedding_blob != '' LIMIT 2000",
            (event_id,),
        )
        rows = await cursor.fetchall()

    scored: list[dict[str, Any]] = []
    for r in rows:
        vec = gemini.decode_vector(r["embedding_blob"])
        sim = gemini.cosine_similarity(target_vec, vec)
        scored.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "destination": r["destination"],
            "decision": r["decision"],
            "severity": r["severity"],
            "categories": loads(r["categories_json"], []),
            "prompt_excerpt": r["prompt_excerpt"],
            "similarity": round(sim, 4),
        })
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return {"event_id": event_id, "neighbors": scored[:k]}


# ─── Search-grounded threat intel enrichment ──────────────────────────────────

@router.post("/events/{event_id}/enrich/threat-intel")
async def enrich_threat_intel(event_id: str) -> dict:
    """Use Gemini 2.5 Pro with the google_search tool to fetch current threat
    intel for the credential type involved in this event.

    Returns rotation steps, recent breaches, threat-actor notes, and an
    immediate-action checklist — every claim grounded against Google Search.
    """
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT id, lt_rule, categories_json, decision, severity FROM events WHERE id = ?",
            (event_id,),
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    cats = loads(row["categories_json"], [])
    cred_type = "unknown credential"
    if row["lt_rule"]:
        cred_type = row["lt_rule"].replace("block_", "").replace("_", " ")
    elif "credentials" in cats:
        cred_type = "credential token"
    intel = await gemini.enrich_threat_intel(cred_type, row["lt_rule"])
    return {"event_id": event_id, "credential_type": cred_type, "threat_intel": intel}


# ─── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsSummary)
async def stats(window_hours: int = Query(24, ge=1, le=24 * 30)) -> StatsSummary:
    since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    async with get_db() as db:
        rows = await (
            await db.execute("SELECT * FROM events WHERE timestamp >= ?", (since,))
        ).fetchall()

    by_decision: dict[str, int] = {"allow": 0, "redact": 0, "block": 0}
    by_severity: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    by_category: dict[str, int] = {}
    by_destination: dict[str, int] = {}
    overrides = 0

    for r in rows:
        by_decision[r["decision"]] = by_decision.get(r["decision"], 0) + 1
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1
        by_destination[r["destination"]] = by_destination.get(r["destination"], 0) + 1
        for cat in loads(r["categories_json"], []) or []:
            if cat == "none":
                continue
            by_category[cat] = by_category.get(cat, 0) + 1
        if r["override_applied"]:
            overrides += 1

    return StatsSummary(
        total_events=len(rows),
        by_decision=by_decision,
        by_severity=by_severity,
        by_category=by_category,
        by_destination=by_destination,
        overrides_applied=overrides,
        window_hours=window_hours,
    )


# ─── Narrative (vanilla and agentic) ──────────────────────────────────────────

async def _digest_recent(window_hours: int) -> list[dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    async with get_db() as db:
        rows = await (
            await db.execute(
                """
                SELECT id, timestamp, destination, decision, severity, categories_json,
                       lt_rule, override_applied
                FROM events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 500
                """,
                (since,),
            )
        ).fetchall()
    digest: list[dict[str, Any]] = []
    for r in rows:
        digest.append({
            "ts": r["timestamp"],
            "dest": r["destination"],
            "decision": r["decision"],
            "severity": r["severity"],
            "categories": loads(r["categories_json"], []),
            "lt_rule": r["lt_rule"],
            "override": bool(r["override_applied"]),
        })
    return digest


@router.post("/stats/narrative")
async def narrative(window_hours: int = 24) -> dict:
    digest = await _digest_recent(window_hours)
    text = await gemini.narrate(json.dumps(digest))
    return {"narrative": text, "events_considered": len(digest), "window_hours": window_hours}


@router.post("/stats/narrative/agentic")
async def agentic_narrative(window_hours: int = 24) -> dict:
    """Agentic version: Gemini investigates using function-calling against our own
    audit endpoints before writing the brief. Returns the brief PLUS the trace
    of tool calls so the CISO can see *how* the agent reached its conclusion.
    """
    async def tool_runner(name: str, args: dict[str, Any]) -> Any:
        if name == "get_stats":
            return (await stats(window_hours=args.get("window_hours", window_hours))).model_dump()
        if name == "list_recent_events":
            decision = args.get("decision")
            limit = int(args.get("limit", 10))
            hours = int(args.get("hours", window_hours))
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            where: list[str] = ["timestamp >= ?"]
            params: list = [since]
            if decision:
                where.append("decision = ?")
                params.append(decision)
            sql = "SELECT * FROM events WHERE " + " AND ".join(where) + " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            async with get_db() as db:
                rows = await (await db.execute(sql, tuple(params))).fetchall()
            return [{
                "id": r["id"],
                "timestamp": r["timestamp"],
                "destination": r["destination"],
                "decision": r["decision"],
                "severity": r["severity"],
                "lt_rule": r["lt_rule"],
                "categories": loads(r["categories_json"], []),
            } for r in rows]
        if name == "get_event_detail":
            try:
                ev = await get_event(args["event_id"])
                return ev.model_dump(mode="json")
            except HTTPException:
                return {"error": "event not found"}
        return {"error": f"unknown tool {name!r}"}

    result = await gemini.agentic_narrate(tool_runner)
    result["window_hours"] = window_hours
    return result


@router.get("/policy/rules")
async def policy_rules() -> dict:
    return {"rules": rule_summary()}
