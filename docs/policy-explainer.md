<!-- SPDX-License-Identifier: MIT -->
# Lobster Trap policy walkthrough

Every rule in [`lobster_trap/policy.yaml`](../lobster_trap/policy.yaml) maps to a specific data-class exfiltration risk documented in the LayerX 2026 Enterprise Browser Security Report. This file is the human-readable explainer judges (and security architects) read alongside the YAML.

## Reading the YAML

```yaml
- name: <unique identifier referenced from the dashboard>
  description: <one-line rationale>
  priority: <0–100; higher wins ties>
  action: ALLOW | REDACT | DENY | FLAG
  conditions:
    - field: body
      match_type: regex
      value: "<regex>"
```

`ALLOW` is the policy default. `DENY` hard-blocks. `REDACT` rewrites the matched substring with a placeholder. `FLAG` hands the decision off to Gemini for semantic classification.

---

## CRITICAL (priority 95–100) — hard-block credentials

These never have a legitimate reason to appear in a public-LLM prompt. False positives are accepted as the cost of preventing token leakage.

| Rule | Why DENY | False-positive risk |
|---|---|---|
| `block_aws_access_key` | AWS access keys grant programmatic IAM — the prototypical exfiltration vector | Pasting a fake AKIA-prefixed example from docs |
| `block_aws_secret_key` | Pairs with above for full sigv4 signing power | An unrelated 40-char base64 string near the literal `aws_secret_access_key` |
| `block_private_key_pem` | PEM/SSH/PGP private keys = full-trust impersonation | Pasting a public key by accident is fine — only `PRIVATE KEY` triggers |
| `block_jwt_bearer` | A leaked JWT often = full session takeover; very high false-negative cost | Long base64-segmented strings unrelated to JWTs (rare in body) |
| `block_github_pat` | GitHub PATs grant repo + Actions scopes; ghp_/github_pat_ prefixes are diagnostic | Pasting a token shape from documentation |
| `block_db_connection_string` | Server + User + Pwd triplet = working DB credentials | Tutorial connection strings using literal `password=...` |
| `block_slack_token` | Slack bot/user tokens read message history | Posting a `xoxb-` example from API docs |
| `block_google_api_key` | GCP/Maps/Firebase keys are usable from anywhere | `AIza` substrings in unrelated text (40+ char specificity reduces this) |
| `block_stripe_key` | Stripe live keys grant payment intent control | Documentation snippets — block is still right call |

## HIGH (priority 70–80) — redact regulated PII

Blocking is too aggressive — employees legitimately need help with customer data. Redaction preserves the question while removing the personal data.

| Rule | What it catches | Regulation |
|---|---|---|
| `redact_us_ssn` | XXX-XX-XXXX format, excluding known invalid ranges | SOX, GLBA, employer recordkeeping |
| `redact_credit_card` | 13–16 digit groups | PCI-DSS |
| `redact_email_addresses` | RFC-loose email pattern | GDPR Art. 32, CCPA |
| `redact_phone_numbers_us` | NANP format with optional +1 | GDPR / CCPA |
| `redact_iban` | International bank account number | GDPR / PSD2 / SOX |

Note: the regex is intentionally permissive at this layer — Gemini gets the redacted output as input to the semantic classifier, so false-positive redactions self-heal.

## MEDIUM (priority 55–65) — flag for Gemini

Regex cannot decide whether code is proprietary or whether a column header is just a tutorial. `FLAG` tells LT to allow the prompt through but signal Gemini to perform semantic classification.

| Rule | What it catches | Why FLAG and not REDACT |
|---|---|---|
| `flag_source_code_indicators` | `function/class/import/def/package` line starts | Most code is tutorial-grade; only proprietary code should be sanitized |
| `flag_internal_hostnames` | `*.internal`, `*.corp`, `*.local`, `*.intra` | Internal URLs are signal but not always sensitive |
| `flag_customer_record_columns` | CRM-shaped column headers | A tutorial might also use `customer_id` — Gemini disambiguates |
| `flag_phi_markers` | ICD-10, MRN, DOB, prescription markers | HIPAA exposure — Gemini classifies as `medical` |
| `flag_strategy_or_finance_markers` | Q-forecast, M&A, term sheet, earnings preview | MNPI — Gemini classifies as `strategic`/`legal` |
| `flag_prompt_injection_attempt` | "ignore previous instructions", system-prompt scaffolding | Detection ≠ block; Conduit logs the attempt and lets the downstream LLM decide |

## Built-in detectors

These ride alongside the explicit rules and are always on:

```yaml
detect_prompt_injection: true
detect_credential_exposure: true
detect_pii_leakage: true
detect_data_exfiltration: true
```

They give breadth coverage — a credential pattern not on our explicit list still trips the built-in.

## Egress rules (defense-in-depth)

When Gemini responds, Lobster Trap inspects the response *before* the backend persists it. This prevents:

- A poisoned model that smuggles credentials back into our audit log.
- A model that echoes PII we just sanitized.

| Rule | What it catches |
|---|---|
| `block_credential_emission` | A credential pattern appearing in the model's *response* |
| `block_response_pii_echo` | Emails echoed back; redacted before persistence |

## Network policy

```yaml
allow_domains: [generativelanguage.googleapis.com]
deny_domains: ["*"]
```

The backend's only legitimate outbound is Gemini through LT. Any other outbound — for example, an exfil callback hidden inside a future poisoned LLM response — is denied at the network layer. This is what makes `test_no_direct_gemini.py` load-bearing: if a developer ever bypasses the proxy in code, the network policy stops the connection at runtime too.

---

## How to extend

Add a new rule to `ingress_rules` with a unique `name` and `priority`. The dashboard auto-discovers it via `GET /policy/rules`. The adversarial test suite has a parameterized template — drop a JSONL line in `backend/tests/adversarial.jsonl` and `pytest` validates the new rule end-to-end.
