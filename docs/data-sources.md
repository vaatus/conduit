<!-- SPDX-License-Identifier: MIT -->
# Data sources for the Conduit pitch

Every claim in the README and on the pitch slide is sourced. Citations live here so judges and prospective deployers can verify the wedge.

| Claim | Source | Year | URL |
|---|---|---|---|
| 98% of organizations report unsanctioned AI use | CrowdStrike Global Threat Report | 2026 | https://www.crowdstrike.com/global-threat-report/ |
| 71.6% of enterprise access to GenAI tools is via personal accounts | LayerX Enterprise Browser Security Report | 2026 | https://layerxsecurity.com/enterprise-browser-security-report-2026/ |
| 77% of employees paste data into GenAI; 50% of those pastes contain corporate data | LayerX Browser Security Report | 2025 | https://layerxsecurity.com/browser-security-report-2025/ |
| $670K average breach-cost premium when shadow AI is involved | BlackFog State of Ransomware (IBM/Ponemon-derived) | 2026 | https://www.blackfog.com/the-state-of-ransomware-2026/ |
| Gartner: AI governance spend $492M (2026) → $1B+ (2030) | Gartner forecast | Q1 2026 | https://www.gartner.com/en/newsroom/ |
| 73% of orgs detect unauthorized AI; only 28% have monitoring | Microsoft Internal Threat Intelligence | 2026 | https://www.microsoft.com/en-us/security/blog/ |
| 1-in-6 enterprise users runs an AI browser extension; 73% have high/critical scope | LayerX 2026 (extension permissioning section) | 2026 | https://layerxsecurity.com/enterprise-browser-security-report-2026/ |
| 95% of enterprise GenAI pilots produce no P&L impact | MIT NANDA, *State of AI in Business 2025* | 2025 | https://nanda.media.mit.edu/2025-state-of-ai-business/ |

## On the Lobster Trap framing

> Veea's Lobster Trap is canonically used to filter prompts headed to *your own* agent.
> Conduit reverses the polarity: filtering corporate prompts headed to *public* LLMs.
> Same engine, different direction, 100× the addressable surface.

This framing is the wedge that survives competitor pressure: Microsoft Purview / Entra are identity-bound and miss personal-account access (71.6%). CASB/SSE (Cato, BlackFog, Netskope) see HTTPS but cannot inspect content inside TLS. LayerX is the closest commercial competitor but ships as a closed-source enterprise SKU with no policy-as-code, no semantic redaction, and no Lobster Trap integration.

## On the regulatory hooks

- **GDPR Art. 32** — security of processing. PII leaving the corporate boundary into an LLM provider's tenant is a processing event the controller must document and minimize. Conduit's audit log is that documentation.
- **HIPAA §164.502** — minimum necessary disclosures. PHI pasted into a public LLM is by definition not minimum-necessary.
- **SOX §404** — material weakness controls. MNPI (forecasts, M&A) pasted to a public LLM ahead of disclosure is a §404 issue.
- **PCI-DSS Req 4** — protect cardholder data in transit. Pasting a card number into ChatGPT crosses the CDE boundary.

The `regulatory_concern` field on every Conduit event tags which regime the violation triggers, which is the literal language a regulator would use.
