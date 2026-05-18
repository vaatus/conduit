#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for service in lt backend dashboard; do
  pidfile="$ROOT/scripts/pids/$service.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "→ stopping $service (pid $pid)"
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
done
# belt-and-braces port cleanup
for port in 8000 8001 3000; do
  lsof -i :$port -t 2>/dev/null | xargs -r kill -9 2>/dev/null || true
done
echo "✓ stack stopped"
