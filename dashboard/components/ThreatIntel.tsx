// SPDX-License-Identifier: MIT
'use client';

import { useState } from 'react';
import { fetchThreatIntel, type ThreatIntel as ThreatIntelType } from '@/lib/api';

export function ThreatIntel({ eventId }: { eventId: string }) {
  const [intel, setIntel] = useState<ThreatIntelType | null>(null);
  const [credType, setCredType] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchThreatIntel(eventId);
      setIntel(r.threat_intel);
      setCredType(r.credential_type);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-sm font-semibold text-ink-900">Threat-intel enrichment</div>
          <p className="text-xs text-ink-500">Gemini 2.5 Pro + Google Search grounding · rotation steps + recent breaches + actor notes.</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="text-xs font-medium px-3 py-1.5 rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? 'Researching…' : intel ? 'Re-research' : 'Enrich with Gemini Search'}
        </button>
      </div>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {intel && (
        <div className="mt-3 space-y-4 text-sm">
          {credType && <p className="text-xs text-ink-500">Credential type: <code className="font-mono">{credType}</code></p>}
          <div>
            <div className="text-xs font-semibold text-ink-900 uppercase tracking-wide">Rotation steps</div>
            <pre className="text-xs whitespace-pre-wrap font-mono bg-ink-50 rounded-md p-3 mt-1">{intel.rotation_steps}</pre>
          </div>
          <div>
            <div className="text-xs font-semibold text-ink-900 uppercase tracking-wide">Immediate actions</div>
            <ul className="list-disc list-inside text-sm mt-1 space-y-1">
              {intel.immediate_actions.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
          {intel.recent_breaches && intel.recent_breaches.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-ink-900 uppercase tracking-wide">Recent breaches</div>
              <ul className="space-y-1 text-sm mt-1">
                {intel.recent_breaches.map((b, i) => (
                  <li key={i}>
                    <a href={b.url} target="_blank" rel="noreferrer" className="text-violet-700 underline">{b.name}</a>
                    <span className="text-ink-500"> · {b.date} — {b.summary}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {intel.threat_actor_notes && (
            <div>
              <div className="text-xs font-semibold text-ink-900 uppercase tracking-wide">Threat actors</div>
              <p className="text-sm text-ink-700 mt-1">{intel.threat_actor_notes}</p>
            </div>
          )}
          {intel.sources && intel.sources.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-ink-900 uppercase tracking-wide">Sources (grounded against Google Search)</div>
              <ul className="text-xs mt-1 space-y-1 break-all">
                {intel.sources.map((s, i) => (
                  <li key={i}><a href={s} target="_blank" rel="noreferrer" className="text-violet-700 underline">{s}</a></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
