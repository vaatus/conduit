// SPDX-License-Identifier: MIT
'use client';

import { useEffect, useState } from 'react';
import { fetchStats, type StatsSummary } from '@/lib/api';
import { Card, CardBody, CardHeader, StatTile } from './Card';
import { CategoryDonut } from './CategoryDonut';
import { DomainBars } from './DomainBars';
import { SeverityBars } from './SeverityBars';

export function StatsPanel() {
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const r = await fetchStats(24);
        if (!stop) setStats(r);
      } catch (e) {
        if (!stop) setError(String(e));
      }
    }
    tick();
    const iv = setInterval(tick, 5000);
    return () => { stop = true; clearInterval(iv); };
  }, []);

  if (error) {
    return (
      <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
        Could not load /stats: <code className="font-mono text-xs">{error}</code>
      </div>
    );
  }
  if (!stats) {
    return <div className="text-sm text-ink-500">Loading stats…</div>;
  }

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Events (24h)" value={stats.total_events} />
        <StatTile label="Blocked" value={stats.by_decision.block || 0} accent="text-rose-700" />
        <StatTile label="Redacted" value={stats.by_decision.redact || 0} accent="text-amber-700" />
        <StatTile label="Overrides" value={stats.overrides_applied} accent="text-orange-700" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader title="By category" hint="Top-of-funnel — what kind of data did we catch?" />
          <CardBody><CategoryDonut data={stats.by_category} /></CardBody>
        </Card>
        <Card>
          <CardHeader title="By destination" hint="Which public LLMs are receiving (or attempting to receive) corp data" />
          <CardBody><DomainBars data={stats.by_destination} /></CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="By severity" hint="Critical bars are the ones the CISO wants to know about first." />
        <CardBody><SeverityBars data={stats.by_severity} /></CardBody>
      </Card>
    </>
  );
}
