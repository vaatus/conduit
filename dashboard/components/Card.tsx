// SPDX-License-Identifier: MIT
import { cn } from '@/lib/utils';

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('rounded-xl border bg-white shadow-sm', className)}>{children}</div>;
}

export function CardHeader({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        {hint && <p className="text-xs text-ink-500 mt-0.5">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('p-5', className)}>{children}</div>;
}

export function StatTile({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-xl border bg-white px-5 py-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-ink-500">{label}</div>
      <div className={cn('mt-2 text-2xl font-semibold tracking-tight text-ink-900', accent)}>{value}</div>
    </div>
  );
}
