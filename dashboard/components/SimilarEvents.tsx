// SPDX-License-Identifier: MIT
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { fetchSimilar, type SimilarNeighbor } from '@/lib/api';
import { DecisionBadge, Pill, SeverityBadge } from './Badge';

export function SimilarEvents({ eventId }: { eventId: string }) {
  const [rows, setRows] = useState<SimilarNeighbor[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    setNote(null);
    try {
      const r = await fetchSimilar(eventId, 5);
      setRows(r.neighbors);
      if (r.note) setNote(r.note);
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
          <div className="text-sm font-semibold text-ink-900">Similar past events</div>
          <p className="text-xs text-ink-500">Cosine k-NN over Gemini embeddings — finds prior incidents with the same pattern.</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="text-xs font-medium px-3 py-1.5 rounded-md bg-ink-900 text-white hover:bg-ink-700 disabled:opacity-50"
        >
          {loading ? 'Searching…' : rows ? 'Refresh' : 'Find similar'}
        </button>
      </div>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {note && <p className="text-sm text-ink-500 mt-2">{note}</p>}
      {rows && rows.length === 0 && !note && (
        <p className="text-sm text-ink-500 mt-2">No similar events found in the audit log.</p>
      )}
      {rows && rows.length > 0 && (
        <ul className="divide-y border rounded-lg mt-2">
          {rows.map((n) => (
            <li key={n.id} className="px-3 py-2 hover:bg-ink-50">
              <Link href={`/events/${n.id}`} className="flex items-start gap-3 text-sm">
                <div className="min-w-[60px] text-right">
                  <span className="font-mono text-xs text-ink-700">{(n.similarity * 100).toFixed(1)}%</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap gap-2 items-center mb-1">
                    <DecisionBadge decision={n.decision} />
                    <SeverityBadge severity={n.severity} />
                    {n.categories.filter((c) => c !== 'none').map((c) => <Pill key={c}>{c}</Pill>)}
                    <span className="text-[11px] text-ink-500">→ {n.destination}</span>
                  </div>
                  <div className="font-mono text-[12px] text-ink-700 truncate">{n.prompt_excerpt.slice(0, 140)}{n.prompt_excerpt.length > 140 ? '…' : ''}</div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
