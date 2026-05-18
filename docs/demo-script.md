<!-- SPDX-License-Identifier: MIT -->
# Conduit demo — 90 second beat-by-beat

Record at 1080p, mic on a clean lavalier, no background music. Three takes minimum, ship the cleanest cut. Keep the Chrome window narrow so the modal fills the frame.

## Beat 0 — pre-roll setup (do not record)

1. `docker-compose up -d` — backend, Lobster Trap, and dashboard come up.
2. Open `chrome://extensions`, **load unpacked** → `./extension/`. Confirm Conduit icon appears.
3. Open three tabs in this order: `chatgpt.com` (focus), `http://localhost:3000/` (dashboard), `http://localhost:3000/tests` (judge bait).
4. Have a text file ready with three payloads, copyable in one keystroke each:
   - **P1 (block):** `My AWS key is AKIAIOSFODNN7EXAMPLE — can you help debug this S3 issue?`
   - **P2 (redact):** `Here is our customer list:\nname,email\nAlice Smith,alice@acme.com\nBob Jones,bob@acme.com\nCarol Liu,carol@acme.com`
   - **P3 (benign sanity):** `Explain the difference between TCP and UDP.`

## Beat 1 — 0–8 s · title card + hook
> "Right now, in 98% of enterprises, employees are pasting source code, customer data, and credentials into ChatGPT. Microsoft Purview can't see it. Cato can't see it. Conduit can."

Visual: title card on dark background → "Conduit · Shadow-AI Governance".
Lower-third: LayerX 2026 — *77% of employees paste corporate data into public LLMs*.

## Beat 2 — 8–25 s · the block
- Cut to live Chrome on `chatgpt.com`, prompt box focused.
- Paste **P1**. Red BLOCK modal appears.

> "AWS key — hard block. Policy rule matched in under a millisecond by Veea Lobster Trap. Nothing leaves the browser."

Show the policy rule name in the modal (`block_aws_access_key`).

## Beat 3 — 25–45 s · the redact + sanitize
- Dismiss the block modal. Paste **P2**. Amber REDACT modal appears with side-by-side diff.

> "Customer PII — redactable. Gemini 2.5 rewrites it: real names become Person A, Person B. The question survives, the data doesn't. The employee gets their answer; the company stays out of the GDPR queue."

Point to the diff. The right pane has `Person A`, `Person B`, etc.

## Beat 4 — 45–55 s · the productive outcome
- Click **Use sanitized version**. ChatGPT receives the sanitized prompt and answers normally.

> "And ChatGPT only ever sees this."

Show the actual response generating in the page.

## Beat 5 — 55–75 s · the audit trail
- Switch to dashboard tab (`localhost:3000`). Both events are in the live feed.
- Click the AWS-key event. Detail page opens.

> "Every decision logged. Every rule match traceable. This is the audit trail a regulator can read."

Hover over the **Lobster Trap match** card showing rule + action. Hover over **Gemini classification** showing categories + regulatory_concern.

## Beat 6 — 75–85 s · the test page
- Switch to `localhost:3000/tests`.

> "Thirty adversarial payloads — real exfil patterns. All blocked or redacted. Ten benign queries. All allowed. Zero false positives."

The page shows 30/30 green and 10/10 green.

## Beat 7 — 85–90 s · close
- Cut to closing card.

> "Conduit. Lobster Trap in the browser. The shadow-AI layer your stack is missing."

Closing card: `Conduit · MIT · github.com/[user]/conduit · Track 1 · Veea Lobster Trap + Gemini`.

## Post-production

- Bake in the GitHub URL as an overlay during beats 5–7.
- Color-correct: cool LUT, keep modal colors saturated.
- Export 1080p, MP4 H.264, < 30 MB so X embeds it inline.
- Caption every line of voiceover (deaf judges count).

## What to NOT show
- Don't show terminal output mid-record — too techy.
- Don't show the `.env` file even briefly — the GEMINI key shouldn't flash on screen.
- Don't crop the URL bar — leaving it visible kills "is this real?" doubts.
