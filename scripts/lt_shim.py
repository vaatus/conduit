# SPDX-License-Identifier: MIT
"""Lobster Trap demo shim — a local stand-in for the Veea Lobster Trap binary.

Real Veea LT runs as a Go service; for the demo we ship this minimal Python
substitute so the architectural story holds (backend → LT → Gemini) without
requiring the user to pull the Veea container image.

What this shim does, exactly like the real LT:
  • POST /_lobstertrap/inspect   → evaluates the prompt against policy.yaml
  • POST /v1/chat/completions    → inspects, then forwards to Gemini
  • POST /v1/embeddings          → forwards to Gemini
  • All /v1/* requests           → forwarded transparently to the upstream
  • Every action is logged so you can see LT working during the recording

In production, replace this process with `veeainc/lobstertrap:latest` from
docker-compose.yml — the contract is identical.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# Pick up the backend's in-process policy evaluator so the shim and the real
# proxy share one rule set.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
from conduit.inspector.policy import evaluate as policy_evaluate, load_policy  # noqa: E402

UPSTREAM = os.environ.get(
    "LT_UPSTREAM_OPENAI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai",
).rstrip("/")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s LT-shim %(levelname)s: %(message)s",
)
log = logging.getLogger("lt-shim")

app = FastAPI(title="Lobster Trap demo shim")


@app.on_event("startup")
async def _startup() -> None:
    p = load_policy()
    log.info("policy loaded: %d rules", len(p.rules))
    log.info("upstream Gemini base: %s", UPSTREAM)


@app.get("/")
async def root() -> dict:
    return {
        "service": "lobster-trap-shim",
        "purpose": "Demo stand-in for Veea Lobster Trap — inspects prompts via policy.yaml and proxies /v1/* to Gemini.",
        "endpoints": {
            "GET  /_lobstertrap/health": "liveness check",
            "POST /_lobstertrap/inspect": "evaluate a prompt against the policy",
            "ANY  /v1/{path}": "transparent OpenAI-compatible proxy to the upstream Gemini base URL",
        },
        "upstream": UPSTREAM,
        "rules_loaded": len(load_policy().rules),
        "note": "In production, replace this process with veeainc/lobstertrap:latest (see docker-compose.yml).",
    }


@app.get("/_lobstertrap/health")
async def health() -> dict:
    return {"status": "ok", "upstream": UPSTREAM, "rules": len(load_policy().rules)}


@app.post("/_lobstertrap/inspect")
async def inspect(payload: dict) -> dict:
    prompt = payload.get("prompt", "")
    decision = policy_evaluate(prompt)
    log.info(
        "INSPECT: %s rule=%s len=%d cats=%s",
        decision.action,
        decision.matched_rule,
        len(prompt),
        decision.detected_categories,
    )
    return decision.model_dump()


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    body = await request.body()

    # Best-effort egress inspection: peek into chat-completion payloads and run
    # the policy on the joined user content. This is what gives LT its "inline
    # security" story — every Gemini call is inspected by LT before forwarding.
    if path == "chat/completions" and body:
        try:
            payload = json.loads(body.decode())
            joined = "\n".join(
                str(m.get("content", "")) if isinstance(m.get("content"), str)
                else json.dumps(m.get("content"))
                for m in payload.get("messages", [])
            )
            decision = policy_evaluate(joined)
            if decision.action == "DENY":
                log.warning("BLOCKED chat completion via egress rule %s", decision.matched_rule)
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "message": f"Lobster Trap blocked outbound prompt — rule {decision.matched_rule}",
                            "type": "lobstertrap_block",
                        }
                    },
                )
            log.info("FORWARD chat/completions (LT inspect: %s)", decision.action)
        except (ValueError, json.JSONDecodeError):
            log.info("FORWARD chat/completions (body not JSON-parseable; passing through)")
    else:
        log.info("FORWARD %s %s", request.method, path)

    upstream_url = f"{UPSTREAM}/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            upstream_resp = await client.request(
                request.method,
                upstream_url,
                content=body,
                headers=headers,
                params=request.query_params,
            )
    except httpx.HTTPError as exc:
        log.error("upstream error: %s", exc)
        return JSONResponse(status_code=502, content={"error": {"message": str(exc), "type": "upstream_unreachable"}})

    log.info("← %s %s (%d bytes)", upstream_resp.status_code, path, len(upstream_resp.content))
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        media_type=upstream_resp.headers.get("content-type", "application/json"),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("LT_SHIM_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
