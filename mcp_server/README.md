<!-- SPDX-License-Identifier: MIT -->
# Conduit MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Conduit's shadow-AI governance surface to AI agents. Plugs into Claude Desktop, internal copilots, Slack bots, incident-response agents — anything that speaks MCP.

## Why MCP

Conduit's browser extension catches paste events at the moment they happen. But **the audit trail it produces is the durable asset**: it's the regulator-readable record of every prompt that tried to leave the corporate boundary.

This MCP server makes that audit trail *conversable*. A CISO can ask their own AI agent:

> "Has anything critical leaked through ChatGPT in the last 24 hours?"
> "Audit the policy: what class of data are we missing?"
> "Inspect this draft message before I send it to a vendor's AI tool."

…and the agent answers using the same engine the extension uses — Lobster Trap inspection, Gemini classification, the live audit DB.

## Surface

### Tools (callable actions)

| Tool | Purpose |
|---|---|
| `conduit_inspect(prompt, destination?, trigger?)` | Run a full inspection on arbitrary text — same pipeline the extension uses |
| `conduit_list_events(limit?, decision?, destination?, since?)` | Search the audit log with filters |
| `conduit_get_event(event_id)` | Full detail on a single event |
| `conduit_stats(window_hours?)` | Counts by decision / severity / category / destination |
| `conduit_narrate(window_hours?)` | Gemini-generated CISO daily summary paragraph |
| `conduit_policy_rules()` | Active Lobster Trap rules with priorities + descriptions |
| `conduit_mark_override(event_id)` | Stamp an event as override-applied |
| `conduit_health()` | Backend + LT + Gemini config check |

### Resources (read-only artifacts)

| URI | Mime | Contents |
|---|---|---|
| `conduit://policy/yaml` | `application/yaml` | The live `lobster_trap/policy.yaml` |
| `conduit://events/recent` | `application/json` | Last 50 audit events |
| `conduit://stats/today` | `application/json` | 24h rolling stats snapshot |
| `conduit://tests/results` | `text/plain` | The adversarial + benign test results |

### Prompts (templates the agent can invoke)

| Prompt | Use |
|---|---|
| `daily_audit_prompt(hours=24)` | Walks an agent through the morning shadow-AI review |
| `policy_gap_review_prompt()` | Asks the agent to identify a missing rule from the policy + recent events |

## Install

```bash
cd mcp_server
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e .
```

The `conduit-mcp` console script is now on your PATH.

## Run

### stdio (Claude Desktop, mcp-cli, any local MCP client)

```bash
CONDUIT_BACKEND_URL=http://localhost:8001 conduit-mcp
```

### Streamable HTTP (remote agents)

```bash
CONDUIT_BACKEND_URL=http://localhost:8001 \
  MCP_TRANSPORT=http \
  MCP_HTTP_PORT=8765 \
  conduit-mcp
```

Or via docker-compose:

```bash
docker-compose up -d mcp-server   # exposes :8765
```

## Adding to Claude Desktop

Open `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "conduit-mcp",
      "env": {
        "CONDUIT_BACKEND_URL": "http://localhost:8001"
      }
    }
  }
}
```

Restart Claude Desktop. The Conduit tools and resources are now available in the conversation — try asking *"What kind of data did Conduit catch in the last day?"*.

If you installed with `uv`, point at the script with `uvx`:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "uvx",
      "args": ["--from", "/absolute/path/to/conduit/mcp_server", "conduit-mcp"],
      "env": { "CONDUIT_BACKEND_URL": "http://localhost:8001" }
    }
  }
}
```

## Adding to a remote agent over HTTP

Point your MCP client at `http://<host>:8765/mcp` (streamable HTTP) and pass the optional `MCP_AUTH_TOKEN` as a bearer header in production.

## Architecture

```
┌────────────────┐  MCP tools/resources/prompts  ┌─────────────────┐
│   AI agent     │ ────────────────────────────► │  conduit-mcp    │
│ (Claude Desktop│                                │ (FastMCP)       │
│  · Slack bot   │ ◄──────────────────────────── │                 │
│  · copilot)    │       JSON-RPC over stdio/HTTP └────────┬────────┘
└────────────────┘                                          │
                                                            │ HTTP
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Conduit Backend │
                                                   │  (FastAPI)      │
                                                   └────────┬────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────────┐
                                                   │  Lobster Trap   │
                                                   │  + Gemini       │
                                                   └─────────────────┘
```

The MCP server is intentionally a shell — the backend remains the single source of truth for inspection, audit, and policy. This keeps the MCP ↔ backend contract narrow and lets an org run Conduit without MCP, or stand up MCP without redeploying the backend.

## Tests

```bash
.venv/bin/pytest tests/
```

Five smoke tests assert that all 8 tools, 4 resources, and 2 prompts register correctly. Backend isn't hit — these validate the contract an MCP client sees on connect.

## License

MIT.
