// SPDX-License-Identifier: MIT
import fs from 'node:fs/promises';
import path from 'node:path';
import { Card, CardBody, CardHeader } from '@/components/Card';

interface AdvResult {
  id: string;
  expected_decision: string;
  got_decision: string;
  expected_rule?: string | null;
  got_rule?: string | null;
  pass: boolean;
}
interface BenignResult {
  id: string;
  expected_decision: string;
  got_decision: string;
  pass: boolean;
}

export const dynamic = 'force-static';

async function readResults(): Promise<{ adv: AdvResult[]; ben: BenignResult[]; raw: string } | null> {
  const candidates = [
    path.join(process.cwd(), '..', 'backend', 'tests', 'results.txt'),
    path.join(process.cwd(), '..', '..', 'backend', 'tests', 'results.txt'),
    '/data/results.txt',
  ];
  for (const p of candidates) {
    try {
      const raw = await fs.readFile(p, 'utf-8');
      return { ...parse(raw), raw };
    } catch { /* keep trying */ }
  }
  return null;
}

function parse(raw: string): { adv: AdvResult[]; ben: BenignResult[] } {
  const adv: AdvResult[] = [];
  const ben: BenignResult[] = [];
  let section: 'adv' | 'ben' | null = null;
  for (const line of raw.split('\n')) {
    if (line.includes('─── Adversarial detail')) { section = 'adv'; continue; }
    if (line.includes('─── Benign detail')) { section = 'ben'; continue; }
    const m = line.match(/^\s+\[(PASS|FAIL)\]\s+(\S+)\s+expect=(\S+)\s+got=(\S+)(?:\s+rule expect=(\S+)\s+got=(\S+))?/);
    if (!m) continue;
    const pass = m[1] === 'PASS';
    if (section === 'adv') {
      adv.push({
        id: m[2],
        expected_decision: m[3],
        got_decision: m[4],
        expected_rule: m[5] || null,
        got_rule: m[6] || null,
        pass,
      });
    } else if (section === 'ben') {
      ben.push({ id: m[2], expected_decision: m[3], got_decision: m[4], pass });
    }
  }
  return { adv, ben };
}

export default async function TestsPage() {
  const data = await readResults();

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Adversarial test suite</h1>
        <p className="text-sm text-ink-500 mt-1">
          Real exfiltration patterns vs. benign queries. Committed in <code className="font-mono">backend/tests/results.txt</code>, rendered live here.
        </p>
      </section>

      {!data && (
        <Card>
          <CardBody>
            <p className="text-sm text-rose-700">
              Could not find <code className="font-mono">backend/tests/results.txt</code>. Run <code className="font-mono">cd backend &amp;&amp; pytest</code> first.
            </p>
          </CardBody>
        </Card>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <SummaryCard title="Adversarial" passed={data.adv.filter((r) => r.pass).length} total={data.adv.length} />
            <SummaryCard title="Benign" passed={data.ben.filter((r) => r.pass).length} total={data.ben.length} />
          </div>

          <Card>
            <CardHeader title="Adversarial payloads" hint="30 real exfil patterns. Must block credentials. Must redact PII." />
            <CardBody className="p-0">
              <ResultsTable rows={data.adv} kind="adv" />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Benign payloads" hint="10 ordinary queries. Must all be ALLOWED — zero false positives." />
            <CardBody className="p-0">
              <ResultsTable rows={data.ben} kind="ben" />
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

function SummaryCard({ title, passed, total }: { title: string; passed: number; total: number }) {
  const ok = passed === total;
  return (
    <div className={`rounded-xl border p-5 ${ok ? 'bg-emerald-50 border-emerald-200' : 'bg-rose-50 border-rose-200'}`}>
      <div className="text-xs uppercase tracking-wide text-ink-500">{title}</div>
      <div className={`mt-2 text-3xl font-semibold tracking-tight ${ok ? 'text-emerald-700' : 'text-rose-700'}`}>
        {passed} / {total}
      </div>
      <div className={`mt-1 text-xs ${ok ? 'text-emerald-700' : 'text-rose-700'}`}>
        {ok ? 'All passing' : `${total - passed} failure${total - passed === 1 ? '' : 's'}`}
      </div>
    </div>
  );
}

function ResultsTable({ rows, kind }: { rows: (AdvResult | BenignResult)[]; kind: 'adv' | 'ben' }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
          <tr>
            <th className="px-4 py-2 text-left">ID</th>
            <th className="px-4 py-2 text-left">Expected</th>
            <th className="px-4 py-2 text-left">Got</th>
            {kind === 'adv' && <th className="px-4 py-2 text-left">Rule</th>}
            <th className="px-4 py-2 text-right">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => {
            const adv = kind === 'adv' ? (r as AdvResult) : null;
            return (
              <tr key={r.id} className="hover:bg-ink-50">
                <td className="px-4 py-2 font-mono text-xs">{r.id}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.expected_decision}</td>
                <td className="px-4 py-2 font-mono text-xs">{r.got_decision}</td>
                {adv && (
                  <td className="px-4 py-2 font-mono text-xs text-ink-500">
                    {adv.expected_rule ? `${adv.got_rule || '—'} (expect ${adv.expected_rule})` : '—'}
                  </td>
                )}
                <td className="px-4 py-2 text-right">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${r.pass ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                    {r.pass ? 'PASS' : 'FAIL'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
