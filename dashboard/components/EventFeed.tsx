// SPDX-License-Identifier: MIT
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchEvents, relativeTime, type EventRecord } from '@/lib/api';
import { DecisionBadge, Pill, SeverityBadge } from './Badge';

export function EventFeed({ limit = 30, pollMs = 2500 }: { limit?: number; pollMs?: number }) {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const r = await fetchEvents({ limit });
        if (!stop) {
          setEvents(r.events);
          setError(null);
        }
      } catch (e) {
        if (!stop) setError(String(e));
      } finally {
        if (!stop) setLoaded(true);
      }
    }
    tick();
    const iv = setInterval(tick, pollMs);
    return () => { stop = true; clearInterval(iv); };
  }, [limit, pollMs]);

  if (!loaded) {
    return <div className="text-sm text-ink-500">Loading events…</div>;
  }
  if (error) {
    return (
      <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
        Could not load events: <code className="font-mono text-xs">{error}</code>
        <br />Is the backend running on <code>localhost:8001</code>?
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="text-sm text-ink-500 rounded-lg border border-dashed p-6 text-center bg-ink-50">
        No events yet. Paste something into ChatGPT with the extension installed and reload.
      </div>
    );
  }
  return (
    <ul className="divide-y">
      {events.map((e) => (
        <li key={e.id} className="py-3 first:pt-0 last:pb-0">
          <Link href={`/events/${e.id}`} className="flex items-start gap-3 group">
            <div className="flex flex-col items-center min-w-[64px]">
              <DecisionBadge decision={e.decision} />
              <span className="text-[10px] text-ink-500 mt-1">{relativeTime(e.timestamp)}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center flex-wrap gap-2 text-sm">
                <SeverityBadge severity={e.classification.severity} />
                {e.classification.categories.filter((c) => c !== 'none').map((c) => (
                  <Pill key={c}>{c}</Pill>
                ))}
                {e.lt_match?.rule && (
                  <span className="font-mono text-[11px] text-ink-500">rule={e.lt_match.rule}</span>
                )}
                {e.override_applied && (
                  <span className="font-mono text-[11px] text-rose-700">override</span>
                )}
              </div>
              <div className="mt-1 text-sm text-ink-700 truncate">
                <span className="text-ink-500">→ {e.destination}</span>{' '}
                <span className="font-mono text-[12px]">{e.prompt_excerpt.slice(0, 160)}{e.prompt_excerpt.length > 160 ? '…' : ''}</span>
              </div>
            </div>
            <div className="text-[11px] text-ink-400 hidden md:block group-hover:text-ink-700">view →</div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
