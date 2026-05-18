<!-- SPDX-License-Identifier: MIT -->
# Conduit Chrome Extension

Chromium MV3 extension that intercepts paste events on public-LLM domains and routes them through the Conduit backend for inspection.

## Supported sites
- `chatgpt.com` / `chat.openai.com`
- `claude.ai`
- `gemini.google.com`
- `copilot.microsoft.com`
- `www.perplexity.ai`

## Load unpacked (dev)

1. Start the backend: `docker-compose up -d` in the repo root.
2. Open `chrome://extensions` → toggle **Developer mode** on.
3. Click **Load unpacked** → select the `extension/` directory.
4. Pin the Conduit icon next to the URL bar.
5. Open `chatgpt.com`, paste anything ≥ 50 characters → modal appears.

## Configuring the backend URL

The default backend is `http://localhost:8001`. To change it (e.g., when deploying to a corp endpoint), set it via the extension's storage:

```js
chrome.storage.sync.set({ backend: 'https://conduit.yourco.internal' });
```

## Fail-open vs fail-closed

`background.js` returns `decision: 'allow'` if the backend is unreachable. This is the right call for a demo (an outage shouldn't block the user from pasting at all). For prod deployments, flip the catch branch to return `decision: 'block'` so a backend outage refuses unsafe egress instead. README has the one-line patch.

## What lives where

| File | Responsibility |
|---|---|
| `manifest.json` | MV3 declaration; host permissions, content-script match list |
| `content.js` | Paste interception, Shadow-DOM modal lifecycle, text insertion |
| `background.js` | Service worker — talks to the Conduit backend, manages install ID and per-installation pseudo-ID hashing |
| `modal/modal.html` + `modal.css` | Shadow-DOM markup + styles for the three states (allow / redact / block) |
| `icons/` | 16/48/128 PNG icons |

## Privacy

- `user_pseudo_id` is `sha256(install_id)[:12]`. The backend never receives the install ID itself.
- No keyboard logging, no clipboard polling — only the paste body that the user just attempted is sent.
- All traffic is local (`http://localhost:8001`) unless the user configures a different `backend`.
