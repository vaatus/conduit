// SPDX-License-Identifier: MIT
'use client';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts';

const COLORS: Record<string, string> = {
  low: '#16a34a',
  medium: '#ca8a04',
  high: '#ea580c',
  critical: '#dc2626',
};

export function SeverityBars({ data }: { data: Record<string, number> }) {
  const order = ['low', 'medium', 'high', 'critical'];
  const rows = order.map((k) => ({ name: k, value: data[k] || 0 }));
  return (
    <div className="h-[180px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} />
          <YAxis tick={{ fontSize: 11, fill: '#475569' }} allowDecimals={false} />
          <Tooltip cursor={{ fill: 'rgba(15,23,42,.04)' }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {rows.map((r) => <Cell key={r.name} fill={COLORS[r.name]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
