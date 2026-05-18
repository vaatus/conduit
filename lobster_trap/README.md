<!-- SPDX-License-Identifier: MIT -->
# Lobster Trap configuration for Conduit

Conduit uses [Veea Lobster Trap](https://github.com/veeainc/lobstertrap) as the inspection engine sitting between the FastAPI backend and Gemini.

## What lives here

- `policy.yaml` — the corporate-egress policy enforced on every employee paste. Read this first; it is the prize-winning artifact.
- `docker-compose.fragment.yml` — partial compose snippet referenced by the root `docker-compose.yml`.

## What the policy does

| Rule class | Action | Examples |
|---|---|---|
| Credentials & keys | `DENY` (hard block) | AWS keys, GitHub PATs, JWTs, PEM blocks, DB connection strings |
| Regulated PII | `REDACT` (auto-rewrite) | SSN, credit cards, emails, phones, IBANs |
| Sensitive semantics | `FLAG` (hands off to Gemini) | Source-code indicators, internal hostnames, customer-record columns, PHI markers, MNPI |
| Built-ins | `on` | Prompt injection, credential exposure, PII leakage, data exfiltration |

A human-readable, rule-by-rule walkthrough lives at [`../docs/policy-explainer.md`](../docs/policy-explainer.md).

## Why ingress + egress

`ingress_rules` cover the prompt headed *out* to the public LLM — that is Conduit's whole reason for existing. `egress_rules` are defensive: if a poisoned model response tries to smuggle a credential back into our backend logs, LT redacts/denies before we persist it.

## Network policy

The backend has exactly one legitimate outbound destination: `generativelanguage.googleapis.com`. LT denies anything else. This is what makes the `test_no_direct_gemini.py` invariant load-bearing — if the backend ever tries to hit Gemini directly, LT cuts the connection.

## Running Lobster Trap

The root `docker-compose.yml` mounts this directory at `/policies` inside the `lobster-trap` container. If you're running LT bare-metal:

```bash
# clone the upstream once
git clone https://github.com/veeainc/lobstertrap vendor/
cd vendor && go build -o ../lobstertrap ./cmd/lobstertrap

# run with our policy
./lobstertrap proxy --policy ../policy.yaml --port 8000
```

## Mock mode (for dev without the LT binary)

The backend honors `LT_MOCK_MODE=true`, which loads `policy.yaml` and evaluates the regex rules in-process. This keeps the CI suite green and lets the demo run on a laptop that doesn't have the LT image pulled. Production uses the real proxy.
