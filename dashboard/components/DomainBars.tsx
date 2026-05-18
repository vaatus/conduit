// SPDX-License-Identifier: MIT
'use client';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export function DomainBars({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  if (rows.length === 0) {
    return <div className="text-sm text-ink-500 h-[260px] flex items-center justify-center">No events captured yet.</div>;
  }

  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#475569' }} interval={0} angle={-15} textAnchor="end" height={50} />
          <YAxis tick={{ fontSize: 10, fill: '#475569' }} allowDecimals={false} />
          <Tooltip cursor={{ fill: 'rgba(15,23,42,.04)' }} />
          <Bar dataKey="value" fill="#0f172a" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
