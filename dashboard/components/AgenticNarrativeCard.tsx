// SPDX-License-Identifier: MIT
'use client';

import { useState } from 'react';
import { fetchAgenticNarrative, type AgenticNarrative } from '@/lib/api';
import { Card, CardBody, CardHeader } from './Card';

export function AgenticNarrativeCard() {
  const [data, setData] = useState<AgenticNarrative | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchAgenticNarrative(24);
      setData(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Agentic CISO brief"
        hint="Gemini 2.5 Pro investigates with function calling — calls back into Conduit's own audit tools, then writes the brief. Tool-call trace included."
        action={
          <button
            onClick={run}
            disabled={loading}
            className="text-xs font-medium px-3 py-1.5 rounded-md bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {loading ? 'Investigating…' : data ? 'Re-run' : 'Run agentic brief'}
          </button>
        }
      />
      <CardBody>
        {error && <p className="text-sm text-rose-700">{error}</p>}
        {!data && !error && !loading && (
          <p className="text-sm text-ink-500">No agentic narrative yet. Click <em>Run agentic brief</em> — Gemini will investigate the audit log via function calling before writing.</p>
        )}
        {data && (
          <>
            <p className="text-sm leading-6 text-ink-900">{data.narrative}</p>
            <div className="mt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-ink-500 mb-2">
                Tool-call trace ({data.trace.length} call{data.trace.length === 1 ? '' : 's'} · {data.hops ?? 0} hop{data.hops === 1 ? '' : 's'})
              </div>
              <ol className="space-y-1 text-xs">
                {data.trace.map((t, i) => (
                  <li key={i} className="border-l-2 border-violet-300 pl-2">
                    <code className="font-mono text-violet-700">{t.tool}({JSON.stringify(t.args)})</code>
                    <div className="text-ink-500 mt-0.5">{t.result_preview}</div>
                  </li>
                ))}
                {data.trace.length === 0 && (
                  <li className="text-ink-500">No tool calls made — Gemini wrote the brief without investigation.</li>
                )}
              </ol>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
