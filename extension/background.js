// SPDX-License-Identifier: MIT
// Conduit MV3 background service worker.
//
// Role:
//   • Receive INSPECT messages from content.js.
//   • POST the prompt + context to the local Conduit backend.
//   • Return the decision payload to the content script.
//
// Why a service worker:
//   • Cross-origin fetch to localhost:8001 from a content script requires
//     `host_permissions`; routing through the SW makes the host-permission
//     check live in one place and keeps the content script auditable.

const DEFAULT_BACKEND = 'http://localhost:8001';
const INSPECT_PATH = '/inspect';
const OVERRIDE_PATH = '/inspect/override';

async function getBackend() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ backend: DEFAULT_BACKEND }, (cfg) => resolve(cfg.backend));
  });
}

async function getInstallId() {
  return new Promise((resolve) => {
    chrome.storage.local.get({ install_id: null }, (v) => {
      if (v.install_id) return resolve(v.install_id);
      const id = crypto.randomUUID();
      chrome.storage.local.set({ install_id: id }, () => resolve(id));
    });
  });
}

async function sha256Hex(input) {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function userPseudoId() {
  // Non-reversible: hash(install_id). Never PII, never sent.
  const installId = await getInstallId();
  const hex = await sha256Hex(installId);
  return 'u_' + hex.slice(0, 12);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'INSPECT') {
    (async () => {
      try {
        const backend = await getBackend();
        const user_pseudo_id = await userPseudoId();
        const body = {
          prompt: msg.prompt,
          context: { ...msg.context, user_pseudo_id },
        };
        const r = await fetch(backend + INSPECT_PATH, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error(`backend ${r.status}`);
        sendResponse(await r.json());
      } catch (err) {
        // Fail-open in the demo so a backend outage doesn't lock the employee
        // out of pasting. README documents how to switch this to fail-closed.
        sendResponse({ decision: 'allow', error: String(err), classification: { categories: ['none'], severity: 'low' } });
      }
    })();
    return true; // async response
  }

  if (msg.type === 'INSPECT_IMAGE') {
    (async () => {
      try {
        const backend = await getBackend();
        const user_pseudo_id = await userPseudoId();
        const body = {
          image_b64: msg.image_b64,
          image_mime: msg.image_mime || 'image/png',
          context: { ...msg.context, user_pseudo_id },
        };
        const r = await fetch(backend + '/inspect/image', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error(`backend ${r.status}`);
        sendResponse(await r.json());
      } catch (err) {
        sendResponse({ decision: 'allow', error: String(err), classification: { categories: ['none'], severity: 'low' } });
      }
    })();
    return true;
  }

  if (msg.type === 'OVERRIDE') {
    (async () => {
      try {
        const backend = await getBackend();
        await fetch(`${backend}${OVERRIDE_PATH}?event_id=${encodeURIComponent(msg.event_id)}`, {
          method: 'POST',
        });
        sendResponse({ ok: true });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
      }
    })();
    return true;
  }
});

chrome.runtime.onInstalled.addListener(() => {
  // Surface the dashboard so the CISO can confirm install.
  chrome.storage.sync.get({ backend: DEFAULT_BACKEND }, (cfg) => {
    chrome.tabs.create({ url: cfg.backend.replace(':8001', ':3000') });
  });
});
