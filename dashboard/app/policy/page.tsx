// SPDX-License-Identifier: MIT
import fs from 'node:fs/promises';
import path from 'node:path';
import { Card, CardBody, CardHeader } from '@/components/Card';
import { Pill } from '@/components/Badge';
import { fetchRules, type PolicyRule } from '@/lib/api';

export const dynamic = 'force-dynamic';

async function readPolicy(): Promise<string | null> {
  const candidates = [
    path.join(process.cwd(), '..', 'lobster_trap', 'policy.yaml'),
    path.join(process.cwd(), '..', '..', 'lobster_trap', 'policy.yaml'),
    '/policies/policy.yaml',
  ];
  for (const p of candidates) {
    try {
      return await fs.readFile(p, 'utf-8');
    } catch { /* try next */ }
  }
  return null;
}

const ACTION_STYLES: Record<string, string> = {
  DENY:   'bg-rose-100 text-rose-800 ring-rose-200',
  REDACT: 'bg-amber-100 text-amber-800 ring-amber-200',
  FLAG:   'bg-sky-100 text-sky-800 ring-sky-200',
  ALLOW:  'bg-emerald-100 text-emerald-800 ring-emerald-200',
};

export default async function PolicyPage() {
  let rules: PolicyRule[] = [];
  let rulesError: string | null = null;
  try {
    rules = (await fetchRules()).rules;
  } catch (e) {
    rulesError = String(e);
  }
  const yaml = await readPolicy();

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Policy</h1>
        <p className="text-sm text-ink-500 mt-1">
          The Lobster Trap policy that decides every prompt's fate. Each rule maps to a specific exfiltration class.
        </p>
      </section>

      <Card>
        <CardHeader
          title="Active rules"
          hint={rulesError ? `Could not load /policy/rules — using YAML fallback.` : `${rules.length} rules · sorted by priority`}
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2 text-left">Priority</th>
                  <th className="px-4 py-2 text-left">Action</th>
                  <th className="px-4 py-2 text-left">Rule</th>
                  <th className="px-4 py-2 text-left">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rules.map((r) => (
                  <tr key={r.name} className="hover:bg-ink-50">
                    <td className="px-4 py-2 font-mono text-xs">{r.priority}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${ACTION_STYLES[r.action] || ''}`}>
                        {r.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{r.name}</td>
                    <td className="px-4 py-2 text-ink-700">{r.description}</td>
                  </tr>
                ))}
                {rules.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-sm text-ink-500">No rules loaded. Is the backend reachable?</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Policy YAML" hint="The single artifact a Veea judge can read end-to-end." />
        <CardBody>
          {yaml ? (
            <pre className="text-[12px] font-mono whitespace-pre-wrap break-words bg-ink-50 rounded-md p-4 max-h-[60vh] overflow-auto">{yaml}</pre>
          ) : (
            <p className="text-sm text-rose-700">Could not load policy.yaml.</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <Pill>Default action: ALLOW</Pill>
            <Pill>Built-ins on: prompt injection, credentials, PII, exfil</Pill>
            <Pill>Network policy: deny *, allow Gemini only</Pill>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
