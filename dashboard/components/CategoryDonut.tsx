// SPDX-License-Identifier: MIT
'use client';

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const PALETTE = ['#0f172a', '#334155', '#475569', '#64748b', '#94a3b8', '#cbd5e1', '#dc2626', '#ea580c', '#ca8a04', '#16a34a'];

export function CategoryDonut({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }));

  if (rows.length === 0) {
    return <div className="text-sm text-ink-500 h-[260px] flex items-center justify-center">No categorized events in the window.</div>;
  }

  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={rows}
            dataKey="value"
            nameKey="name"
            innerRadius={50}
            outerRadius={85}
            paddingAngle={2}
          >
            {rows.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
          </Pie>
          <Tooltip />
          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
