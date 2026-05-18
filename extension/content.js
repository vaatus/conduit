// SPDX-License-Identifier: MIT
// Conduit MV3 content script — runs on chatgpt.com / claude.ai / gemini.google.com /
// copilot.microsoft.com / www.perplexity.ai.
//
// Responsibilities:
//   • Intercept paste events into the page's prompt input.
//   • Suspend the paste; ask background.js to call /inspect on the backend.
//   • Show a Shadow-DOM modal with the decision (ALLOW toast / REDACT diff / BLOCK).
//   • Insert sanitized text (or the original if the user overrides) on confirm.
//
// Design notes:
//   • Skips pastes under MIN_LEN — most short pastes are commands/queries, not exfil.
//   • Uses capture-phase listener with stopImmediatePropagation so we beat the
//     site's own paste handlers across Gemini/ChatGPT/Claude/Copilot/Perplexity.
//   • DOM resolution uses e.composedPath() + a known-selectors fallback because
//     each host site wraps its prompt input differently (Gemini=rich-textarea,
//     ChatGPT=ProseMirror, Claude=Lexical, Copilot=textarea).

(() => {
  const MIN_LEN = 50;

  // Known prompt-input selectors across supported LLM hosts. Order matters —
  // more specific selectors first.
  const PROMPT_SELECTORS = [
    'rich-textarea .ql-editor',           // Gemini
    '.ql-editor[contenteditable="true"]', // Gemini (alt)
    'div[contenteditable="true"][data-virtualkeyboard="true"]', // Gemini variant
    '#prompt-textarea',                    // ChatGPT classic
    'div[contenteditable="true"].ProseMirror', // ChatGPT (newer)
    'div[contenteditable="true"][data-lexical-editor="true"]',  // Claude
    'div[contenteditable="true"][role="textbox"]',              // Copilot
    'textarea[placeholder]',               // Perplexity (textarea)
    'div[contenteditable="true"]',         // generic fallback
    'textarea',                            // last resort
  ];

  function findEditable(e) {
    // 1) e.composedPath gives the actual path including shadow DOM.
    if (e && typeof e.composedPath === 'function') {
      for (const node of e.composedPath()) {
        if (!node || node === window || node === document) continue;
        if (node.tagName === 'TEXTAREA' || node.tagName === 'INPUT') return node;
        if (node.isContentEditable) return node;
      }
    }
    // 2) e.target ancestors.
    if (e && e.target && e.target.closest) {
      const hit = e.target.closest('[contenteditable="true"], textarea, input');
      if (hit) return hit;
    }
    // 3) document.activeElement (and its descendants for custom-element wrappers).
    const ae = document.activeElement;
    if (ae) {
      if (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT') return ae;
      if (ae.isContentEditable) return ae;
      const inner = ae.querySelector && ae.querySelector('[contenteditable="true"], textarea, input');
      if (inner) return inner;
    }
    // 4) Known-selector fallback for the host LLM.
    for (const sel of PROMPT_SELECTORS) {
      const el = document.querySelector(sel);
      if (el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT' || el.isContentEditable)) return el;
    }
    return null;
  }

  function insertAtCursor(text, target) {
    const el = target || findEditable();
    if (!el) {
      console.warn('Conduit: no paste target found; falling back to clipboard');
      return false;
    }
    el.focus();
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      el.value = el.value.slice(0, start) + text + el.value.slice(end);
      const pos = start + text.length;
      el.selectionStart = el.selectionEnd = pos;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    }
    // contenteditable — execCommand is still the most reliable across React/Lexical/Quill/ProseMirror in 2026.
    try {
      const ok = document.execCommand('insertText', false, text);
      if (ok) {
        el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
        return true;
      }
    } catch { /* fall through */ }
    // Last-ditch fallback: append text node.
    el.textContent = (el.textContent || '') + text;
    el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
    return true;
  }

  // ─── Image-paste interception (multimodal Gemini Vision) ─────────────
  async function handleImagePaste(e, imageItem) {
    console.log('[Conduit] handleImagePaste start; type=', imageItem.type);
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();

    const file = imageItem.getAsFile();
    if (!file) {
      console.warn('[Conduit] imageItem.getAsFile() returned null');
      return false;
    }
    console.log('[Conduit] file size:', file.size, 'bytes');
    const blob = await file.arrayBuffer();
    const b64 = bytesToBase64(new Uint8Array(blob));
    console.log('[Conduit] b64 length:', b64.length);

    const context = {
      destination: location.hostname,
      page_title: document.title,
      trigger: 'image_paste',
      timestamp: new Date().toISOString(),
      char_count: 0,
    };

    const target = findEditable(e);
    let decision;
    try {
      console.log('[Conduit] → sending INSPECT_IMAGE to background');
      decision = await chrome.runtime.sendMessage({
        type: 'INSPECT_IMAGE',
        image_b64: b64,
        image_mime: imageItem.type || 'image/png',
        context,
      });
      console.log('[Conduit] ← background returned:', decision);
    } catch (err) {
      console.error('[Conduit] sendMessage failed:', err);
      return true;
    }
    if (!decision) {
      console.warn('[Conduit] background returned no decision');
      return true;
    }

    console.log('[Conduit] showing modal for decision=', decision.decision);
    await ensureModal();

    if (decision.decision === 'allow') {
      showToastAllow();
      return true;
    }

    if (decision.decision === 'redact' && decision.sanitized_alternative) {
      showImageRedact(decision, {
        onAcceptAlternative: () => insertAtCursor(decision.sanitized_alternative, target),
        onCancel: () => { /* image discarded */ },
      });
      return true;
    }

    showImageBlock(decision, { onClose: () => { /* image discarded */ } });
    return true;
  }

  function bytesToBase64(bytes) {
    let bin = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(bin);
  }

  // ─── Shadow-DOM modal ────────────────────────────────────────────────
  let host = null;
  let shadow = null;
  let modalReady = null;

  async function ensureModal() {
    if (modalReady) return modalReady;
    modalReady = (async () => {
      host = document.createElement('div');
      host.id = 'conduit-modal-host';
      host.style.cssText = 'all: initial; position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;';
      document.documentElement.appendChild(host);
      shadow = host.attachShadow({ mode: 'open' });

      const cssURL = chrome.runtime.getURL('modal/modal.css');
      const css = await fetch(cssURL).then((r) => r.text());
      const htmlURL = chrome.runtime.getURL('modal/modal.html');
      const html = await fetch(htmlURL).then((r) => r.text());

      const style = document.createElement('style');
      style.textContent = css;
      shadow.appendChild(style);
      const wrap = document.createElement('div');
      wrap.innerHTML = html;
      shadow.appendChild(wrap);
    })();
    return modalReady;
  }

  function $$(sel) { return shadow.querySelector(sel); }

  function showToastAllow() {
    const toast = $$('#conduit-toast');
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1400);
  }

  function showRedact(decision, { onAcceptSanitized, onKeepOriginal, onCancel }) {
    const panel = $$('#conduit-redact');
    $$('#conduit-redact-original').textContent = decision._original_preview || '';
    $$('#conduit-redact-sanitized').textContent = decision.sanitized_prompt || '';
    $$('#conduit-redact-categories').textContent =
      (decision.classification?.categories || []).filter((c) => c !== 'none').join(', ') || 'sensitive content';
    $$('#conduit-redact-severity').textContent = decision.classification?.severity || 'medium';
    $$('#conduit-redact-rule').textContent = decision.lt_match?.rule || '—';
    $$('#conduit-redact-audit').textContent = decision.audit_message || '';

    const accept = $$('#conduit-redact-accept');
    const keep = $$('#conduit-redact-keep');
    const cancel = $$('#conduit-redact-cancel');
    const close = () => {
      panel.classList.remove('show');
      accept.replaceWith(accept.cloneNode(true));
      keep.replaceWith(keep.cloneNode(true));
      cancel.replaceWith(cancel.cloneNode(true));
    };
    $$('#conduit-redact-accept').onclick = () => { close(); onAcceptSanitized(); };
    $$('#conduit-redact-keep').onclick = () => { close(); onKeepOriginal(); };
    $$('#conduit-redact-cancel').onclick = () => { close(); onCancel(); };
    panel.classList.add('show');
  }

  function showBlock(decision, { onClose }) {
    const panel = $$('#conduit-block');
    $$('#conduit-block-message').textContent = decision.audit_message || 'Blocked by Conduit.';
    $$('#conduit-block-rule').textContent = decision.lt_match?.rule || '—';
    const closeBtn = $$('#conduit-block-close');
    const close = () => {
      panel.classList.remove('show');
      closeBtn.replaceWith(closeBtn.cloneNode(true));
    };
    $$('#conduit-block-close').onclick = () => { close(); onClose(); };
    panel.classList.add('show');
  }

  function showImageRedact(decision, { onAcceptAlternative, onCancel }) {
    const panel = $$('#conduit-image-redact');
    const analysis = decision.image_analysis || {};
    $$('#conduit-image-ui-type').textContent = analysis.ui_type || 'unknown';
    $$('#conduit-image-severity').textContent = decision.classification?.severity || 'medium';
    $$('#conduit-image-categories').textContent =
      (decision.classification?.categories || []).filter((c) => c !== 'none').join(', ') || 'sensitive screenshot';
    $$('#conduit-image-extracted').textContent = analysis.extracted_text_snippet || '(no readable text)';
    $$('#conduit-image-alternative').textContent = decision.sanitized_alternative || '';
    $$('#conduit-image-audit').textContent = decision.audit_message || '';

    const accept = $$('#conduit-image-accept');
    const cancel = $$('#conduit-image-cancel');
    const close = () => {
      panel.classList.remove('show');
      accept.replaceWith(accept.cloneNode(true));
      cancel.replaceWith(cancel.cloneNode(true));
    };
    $$('#conduit-image-accept').onclick = () => { close(); onAcceptAlternative(); };
    $$('#conduit-image-cancel').onclick = () => { close(); onCancel(); };
    panel.classList.add('show');
  }

  function showImageBlock(decision, { onClose }) {
    const panel = $$('#conduit-image-block');
    const analysis = decision.image_analysis || {};
    $$('#conduit-image-block-ui').textContent = analysis.ui_type || 'unknown';
    $$('#conduit-image-block-message').textContent = decision.audit_message || 'Image blocked by Conduit.';
    const closeBtn = $$('#conduit-image-block-close');
    const close = () => {
      panel.classList.remove('show');
      closeBtn.replaceWith(closeBtn.cloneNode(true));
    };
    $$('#conduit-image-block-close').onclick = () => { close(); onClose(); };
    panel.classList.add('show');
  }

  // ─── Paste interception ──────────────────────────────────────────────
  document.addEventListener('paste', async (e) => {
    console.log('[Conduit] paste event fired on', location.hostname);

    // Image paste path — check clipboardData.items for any image/*.
    const items = e.clipboardData?.items || [];
    console.log('[Conduit] clipboardData items:', Array.from(items).map(i => ({ kind: i.kind, type: i.type })));
    for (const item of items) {
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        console.log('[Conduit] image item detected → handleImagePaste');
        if (await handleImagePaste(e, item)) return;
      }
    }

    const text = e.clipboardData?.getData('text');
    console.log('[Conduit] text length:', text?.length || 0, '(MIN_LEN=', MIN_LEN, ')');
    if (!text || text.length < MIN_LEN) return;

    // Find target editable BEFORE preventing default so we can insert later.
    const target = findEditable(e);

    // Always intercept long pastes on supported domains, even if we can't find
    // the editable yet — Conduit's job is to inspect; the modal will guide the
    // user even if insertion fails.
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();

    const context = {
      destination: location.hostname,
      page_title: document.title,
      trigger: 'paste',
      timestamp: new Date().toISOString(),
      char_count: text.length,
    };

    let decision;
    try {
      decision = await chrome.runtime.sendMessage({ type: 'INSPECT', prompt: text, context });
    } catch (err) {
      // Background not responsive — insert original so the user isn't blocked.
      insertAtCursor(text, target);
      return;
    }
    if (!decision) {
      insertAtCursor(text, target);
      return;
    }
    decision._original_preview = text.slice(0, 800);

    await ensureModal();

    if (decision.decision === 'allow') {
      insertAtCursor(text, target);
      showToastAllow();
      return;
    }

    if (decision.decision === 'redact') {
      showRedact(decision, {
        onAcceptSanitized: () => insertAtCursor(decision.sanitized_prompt || text, target),
        onKeepOriginal: () => {
          chrome.runtime.sendMessage({ type: 'OVERRIDE', event_id: decision.event_id });
          insertAtCursor(text, target);
        },
        onCancel: () => { /* user discards the paste entirely */ },
      });
      return;
    }

    // block
    showBlock(decision, { onClose: () => { /* nothing inserted */ } });
  }, true);

  // Log to console that Conduit is active — easy diagnostic if the modal doesn't appear.
  console.log('[Conduit] content script active on ' + location.hostname);
})();
