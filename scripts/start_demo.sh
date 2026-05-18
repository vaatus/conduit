#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Bring up the full Conduit stack for the demo recording:
#   • Lobster Trap shim on :8000
#   • FastAPI backend on :8001
#   • Next.js dashboard on :3000
# Logs land in scripts/logs/.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p scripts/logs scripts/pids

if [ ! -f .env ]; then
  echo "ERROR: .env not found at $ROOT/.env" >&2
  echo "Copy .env.example and set GEMINI_API_KEY." >&2
  exit 1
fi
set -a
. ./.env
set +a

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "ERROR: GEMINI_API_KEY is empty in .env" >&2
  exit 1
fi

# Kill anything we left running from a previous demo session.
for port in 8000 8001 3000; do
  if lsof -i :$port -t > /dev/null 2>&1; then
    echo "→ killing previous process on :$port"
    lsof -i :$port -t | xargs -r kill -9 2>/dev/null || true
    sleep 0.3
  fi
done

# Fresh demo DB so the recording starts from an empty audit log.
rm -f data/events.db data/events.db-journal
mkdir -p data

echo "→ starting Lobster Trap shim on :8000"
LT_UPSTREAM_OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai" \
  LT_SHIM_PORT=8000 \
  PYTHONPATH="$ROOT/backend" \
  nohup "$ROOT/backend/.venv/bin/python" scripts/lt_shim.py \
    > scripts/logs/lt.log 2>&1 &
echo $! > scripts/pids/lt.pid

echo "→ starting backend on :8001"
LT_MOCK_MODE=false \
  LT_INSPECT_URL="http://127.0.0.1:8000/_lobstertrap/inspect" \
  LT_GEMINI_BASE_URL="http://127.0.0.1:8000/v1/" \
  DB_PATH="$ROOT/data/events.db" \
  GEMINI_API_KEY="$GEMINI_API_KEY" \
  GEMINI_MODEL_CLASSIFY="${GEMINI_MODEL_CLASSIFY:-gemini-2.5-flash}" \
  GEMINI_MODEL_SANITIZE="${GEMINI_MODEL_SANITIZE:-gemini-2.5-pro}" \
  GEMINI_MODEL_NARRATIVE="${GEMINI_MODEL_NARRATIVE:-gemini-2.5-pro}" \
  BACKEND_PORT=8001 \
  PYTHONPATH="$ROOT/backend" \
  nohup "$ROOT/backend/.venv/bin/uvicorn" conduit.main:app \
    --host 127.0.0.1 --port 8001 --log-level info \
    > scripts/logs/backend.log 2>&1 &
echo $! > scripts/pids/backend.pid

echo "→ starting dashboard on :3000"
cd "$ROOT/dashboard"
NEXT_PUBLIC_API="http://127.0.0.1:8001" \
  nohup npx next dev -p 3000 \
    > "$ROOT/scripts/logs/dashboard.log" 2>&1 &
echo $! > "$ROOT/scripts/pids/dashboard.pid"
cd "$ROOT"

# Wait for readiness
echo -n "→ waiting for stack to come up "
for i in $(seq 1 40); do
  lt_ok=$(curl -fsS http://127.0.0.1:8000/_lobstertrap/health >/dev/null 2>&1 && echo y || echo n)
  bk_ok=$(curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1 && echo y || echo n)
  db_ok=$(curl -fsS http://127.0.0.1:3000 >/dev/null 2>&1 && echo y || echo n)
  if [ "$lt_ok" = "y" ] && [ "$bk_ok" = "y" ] && [ "$db_ok" = "y" ]; then
    echo
    echo "✓ stack up"
    break
  fi
  echo -n "."
  sleep 0.5
done

echo
echo "─── readiness ────────────────────────────────────────"
echo "  Lobster Trap shim : http://127.0.0.1:8000/_lobstertrap/health  → $(curl -fsS http://127.0.0.1:8000/_lobstertrap/health 2>/dev/null || echo DOWN)"
echo "  Backend           : http://127.0.0.1:8001/health               → $(curl -fsS http://127.0.0.1:8001/health 2>/dev/null | head -c 80)…"
echo "  Dashboard         : http://127.0.0.1:3000                       → $(curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:3000 || echo DOWN)"
echo
echo "─── logs you can tail (in separate terminals) ────────"
echo "  tail -f $ROOT/scripts/logs/lt.log"
echo "  tail -f $ROOT/scripts/logs/backend.log"
echo "  tail -f $ROOT/scripts/logs/dashboard.log"
echo
echo "→ next: load ./extension unpacked at chrome://extensions and open http://localhost:3000"
echo "→ stop:  scripts/stop_demo.sh"
