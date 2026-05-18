// SPDX-License-Identifier: MIT
import { cn } from '@/lib/utils';
import type { Decision, Severity } from '@/lib/api';

const decisionStyles: Record<Decision, string> = {
  allow:  'bg-emerald-100 text-emerald-800 ring-emerald-200',
  redact: 'bg-amber-100 text-amber-800 ring-amber-200',
  block:  'bg-rose-100 text-rose-800 ring-rose-200',
};

const severityStyles: Record<Severity, string> = {
  low:      'bg-emerald-100 text-emerald-800 ring-emerald-200',
  medium:   'bg-amber-100 text-amber-800 ring-amber-200',
  high:     'bg-orange-100 text-orange-800 ring-orange-200',
  critical: 'bg-rose-100 text-rose-800 ring-rose-200',
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset uppercase tracking-wide', decisionStyles[decision])}>
      {decision}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset uppercase tracking-wide', severityStyles[severity])}>
      {severity}
    </span>
  );
}

export function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-700 ring-1 ring-inset ring-ink-200">
      {children}
    </span>
  );
}
