<!-- SPDX-License-Identifier: MIT -->
# Conduit threat model

A blunt accounting of what Conduit catches, what it doesn't, and the assumptions that hold the design together.

## In scope

| Threat | Vector | Conduit response |
|---|---|---|
| Employee pastes AWS/GitHub/JWT/etc. into a public LLM | Browser paste event on supported domains | Hard-block at `paste`; modal explains why; nothing reaches the LLM |
| Employee pastes customer PII into a public LLM | Browser paste event | Redact via LT; sanitized by Gemini; user accepts or overrides (logged) |
| Employee pastes proprietary source code | Browser paste event | FLAG → Gemini classifies as `source_code`/`intellectual_property` → sanitize |
| Employee pastes MNPI (M&A, forecasts, earnings) | Browser paste event | FLAG → Gemini classifies as `strategic`/`legal` → sanitize |
| Employee pastes PHI (ICD-10, MRN, Rx) | Browser paste event | FLAG → Gemini classifies as `medical`, regulatory_concern=`HIPAA` → sanitize |
| Poisoned LLM response smuggles credentials back to backend | Egress from LT | Egress rule blocks emission |
| Developer accidentally adds a direct Gemini call | Source-code mistake | `test_no_direct_gemini.py` fails build + network policy denies the connection at runtime |

## Out of scope (explicit limitations)

| Limitation | Why we don't address it now | What we'd add later |
|---|---|---|
| **Drag-and-drop file uploads to LLMs** | MV3 file-handler intercept is a separate code path; pastes cover ~80% of LayerX-reported exfil | A second `dragover`/`drop` listener feeding the same `/inspect` endpoint |
| **Voice / typed input** | Voice + typing are slow channels; paste is where bulk exfil happens | Optional `keydown` debouncer for typed-prompt scanning, gated behind a setting |
| **Non-supported LLM domains** | We allow-list known public AI hosts; arbitrary new domains aren't watched | An `unknown-LLM` heuristic listener that fires on `meta[name=ai-app]` markers |
| **Other browsers (Firefox, Safari)** | Chromium covers ~70% of corporate desktops; MV3 polyfill story for Firefox is messy | Port to Firefox MV3 + a Safari `WKContentBlocker`-style ext |
| **End-to-end TLS to backend** | Backend is `http://localhost` for the hackathon | TLS via mTLS-terminating reverse proxy in front of the backend in real deployments |
| **OS-level paste (Cmd+V from outside the browser)** | Browser scope only | A native helper agent is the right tool for OS-wide paste, but it's a different product |
| **Employees uninstalling the extension** | We can't prevent it — endpoint compliance is the customer's existing MDM/EDR responsibility | Document the MDM force-install path for Chromium |
| **Persistent storage on the LLM provider side** | Once accepted, the prompt is the provider's | Conduit's contribution is preventing the leak; remediation post-hoc is a different product |

## Assumptions

1. **Backend is trusted.** Conduit assumes the FastAPI backend runs in the corporate cloud or on a managed device. If the backend is compromised, the audit log is compromised; Conduit's posture is *no worse than your existing logging surface*.
2. **LT runs inline.** All Gemini traffic traverses LT. The CI invariant + network policy make this an enforced architectural fact, not a hope.
3. **`user_pseudo_id` is one-way.** `sha256(install_id)[:12]`. The backend cannot reverse it to a real user identity. If a corp deployment wants linkability for forensics, that mapping is maintained out-of-band in the corp directory.
4. **`MIN_LEN` of 50 is correct.** Short pastes are commands/queries; bulk exfil is longer. Tunable in extension settings.
5. **Fail-open in demo, fail-closed in prod.** The MV3 background returns `decision: 'allow'` on backend errors so a demo doesn't get bricked by a transient outage. README documents the one-line patch to fail-closed in production.

## Adversarial postures Conduit is *not* designed to defeat

- A malicious insider intent on exfiltrating data who deliberately uninstalls the extension and uses a personal device.
- An employee who screenshots data and types it back manually.
- A regulator demanding deletion of historical audit events — Conduit's audit log is append-only by design but retention policy is the customer's call.

The right framing for the CISO buyer: *Conduit makes the easy mistakes hard and creates an audit trail when they happen anyway. It is not a substitute for endpoint compliance, identity governance, or workforce training — it is the missing browser-content-aware layer that none of those three currently provide.*
