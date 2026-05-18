# SPDX-License-Identifier: MIT
"""Local replica of Lobster Trap's rule evaluator.

Lives here for two reasons:
  1. Conduit's `LT_MOCK_MODE` runs without the LT binary — the same rules
     evaluate in-process so the CI suite is green on any laptop.
  2. The dashboard's policy-explainer needs to look up `rule → action`
     mappings without hitting the LT proxy.

The real Lobster Trap remains canonical when `LT_MOCK_MODE=false`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import settings
from ..models.classification import LTAction, LTDecision

_DEFAULT_POLICY_RELATIVE = Path(__file__).parents[3] / "lobster_trap" / "policy.yaml"


@dataclass
class _Rule:
    name: str
    description: str
    action: LTAction
    priority: int
    deny_message: str | None = None
    regex: re.Pattern[str] | None = None
    redact_pattern: re.Pattern[str] | None = None
    redact_with: str | None = None
    category_hint: str = ""


@dataclass
class _Policy:
    rules: list[_Rule] = field(default_factory=list)
    default_action: LTAction = "ALLOW"


def _compile_rule(raw: dict, kind: str) -> _Rule | None:
    name = raw.get("name")
    if not name:
        return None
    action: LTAction = raw.get("action", "ALLOW")
    priority = int(raw.get("priority", 50))
    description = raw.get("description", "")
    deny_message = raw.get("deny_message")

    rgx: re.Pattern[str] | None = None
    if action == "REDACT" and raw.get("redact_pattern"):
        rgx = re.compile(raw["redact_pattern"])
    else:
        for cond in raw.get("conditions", []) or []:
            if cond.get("match_type") == "regex" and cond.get("value"):
                rgx = re.compile(cond["value"])
                break

    return _Rule(
        name=name,
        description=description,
        action=action,
        priority=priority,
        deny_message=deny_message,
        regex=rgx if action in {"DENY", "FLAG"} else None,
        redact_pattern=re.compile(raw["redact_pattern"]) if action == "REDACT" and raw.get("redact_pattern") else None,
        redact_with=raw.get("redact_with"),
        category_hint=_category_from_name(name) if kind == "ingress" else "",
    )


def _category_from_name(rule_name: str) -> str:
    n = rule_name.lower()
    if any(t in n for t in ("aws", "private_key", "jwt", "github_pat", "slack", "google_api", "stripe", "db_connection")):
        return "credentials"
    if any(t in n for t in ("ssn", "credit_card", "email", "phone", "iban")):
        return "customer_pii"
    if "source_code" in n:
        return "source_code"
    if "hostname" in n or "internal" in n:
        return "intellectual_property"
    if "customer_record" in n:
        return "customer_pii"
    if "phi" in n:
        return "medical"
    if "strategy" in n or "finance" in n:
        return "strategic"
    return ""


@lru_cache(maxsize=1)
def load_policy() -> _Policy:
    candidates = [
        Path(settings.LT_POLICY_PATH),
        _DEFAULT_POLICY_RELATIVE,
        Path("/policies/policy.yaml"),
        Path(__file__).resolve().parents[2] / "lobster_trap" / "policy.yaml",
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        return _Policy()

    with src.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    rules: list[_Rule] = []
    for r in raw.get("ingress_rules", []) or []:
        compiled = _compile_rule(r, kind="ingress")
        if compiled:
            rules.append(compiled)
    rules.sort(key=lambda r: r.priority, reverse=True)
    return _Policy(rules=rules, default_action=raw.get("default_action", "ALLOW"))


def reset_policy_cache() -> None:
    load_policy.cache_clear()


def evaluate(prompt: str) -> LTDecision:
    """Return the highest-priority rule decision against `prompt`. Mirrors LT semantics."""
    policy = load_policy()
    if not policy.rules:
        return LTDecision(action="ALLOW", matched_rule=None, intent_classification="unknown")

    # 1. First DENY wins (sorted by priority desc above).
    for rule in policy.rules:
        if rule.action == "DENY" and rule.regex and rule.regex.search(prompt):
            return LTDecision(
                action="DENY",
                matched_rule=rule.name,
                redacted_body=None,
                intent_classification="exfiltration",
                detected_categories=[rule.category_hint] if rule.category_hint else [],
                deny_message=rule.deny_message,
            )

    # 2. Then REDACT — apply all redactions in order, collect matched names.
    redacted = prompt
    redacted_rules: list[str] = []
    categories: set[str] = set()
    for rule in policy.rules:
        if rule.action == "REDACT" and rule.redact_pattern:
            new = rule.redact_pattern.sub(rule.redact_with or "[REDACTED]", redacted)
            if new != redacted:
                redacted = new
                redacted_rules.append(rule.name)
                if rule.category_hint:
                    categories.add(rule.category_hint)
    if redacted_rules:
        return LTDecision(
            action="REDACT",
            matched_rule=redacted_rules[0],
            redacted_body=redacted,
            intent_classification="pii_handling",
            detected_categories=sorted(categories),
        )

    # 3. Then FLAG — hand off to Gemini for semantic decision.
    for rule in policy.rules:
        if rule.action == "FLAG" and rule.regex and rule.regex.search(prompt):
            return LTDecision(
                action="FLAG",
                matched_rule=rule.name,
                intent_classification="needs_semantic_review",
                detected_categories=[rule.category_hint] if rule.category_hint else [],
            )

    return LTDecision(action="ALLOW", matched_rule=None, intent_classification="benign")


def rule_summary() -> list[dict]:
    """Used by the dashboard's /policy/rules endpoint and the explainer doc."""
    p = load_policy()
    return [
        {"name": r.name, "action": r.action, "priority": r.priority, "description": r.description}
        for r in p.rules
    ]
