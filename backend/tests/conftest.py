# SPDX-License-Identifier: MIT
"""Pytest setup — forces LT_MOCK_MODE and a temp DB so tests are hermetic."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LT_MOCK_MODE", "true")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("DB_PATH", str(Path(__file__).parent / ".pytest-events.db"))

POLICY = ROOT.parent / "lobster_trap" / "policy.yaml"
os.environ.setdefault("LT_POLICY_PATH", str(POLICY))
