// SPDX-License-Identifier: MIT
// Thin client for the FastAPI backend. All requests go through Next.js rewrites
// so the dashboard can be deployed behind any reverse proxy without CORS headaches.

export type Decision = 'allow' | 'redact' | 'block';
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type LTAction = 'ALLOW' | 'REDACT' | 'DENY' | 'FLAG';

export interface LTMatch {
  rule: string | null;
  action: LTAction;
}

export interface Classification {
  categories: string[];
  severity: Severity;
  specific_findings: { type: string; snippet_indicator: string; rationale: string }[];
  explanation: string;
  suggest_sanitize: boolean;
  regulatory_concern: string[];
}

export interface ImageAnalysis {
  ui_type: string;
  visible_sensitive_elements: { kind?: string; rationale?: string }[];
  extracted_text_snippet: string;
  suggest_text_alternative: boolean;
}

export interface ReasoningTrace {
  final_severity: string;
  confirmed_categories: string[];
  reasoning_summary: string;
  decision_change: 'confirmed' | 'escalated' | 'downgraded';
}

export interface EventRecord {
  id: string;
  timestamp: string;
  destination: string;
  user_pseudo_id: string;
  page_title: string | null;
  trigger: string;
  char_count: number;
  decision: Decision;
  lt_match: LTMatch | null;
  classification: Classification;
  prompt_excerpt: string;
  sanitized_excerpt: string | null;
  override_applied: boolean;
  audit_message: string | null;
  is_image: boolean;
  image_mime: string | null;
  image_analysis: ImageAnalysis | null;
  reasoning: ReasoningTrace | null;
}

export interface SimilarNeighbor {
  id: string;
  timestamp: string;
  destination: string;
  decision: Decision;
  severity: Severity;
  categories: string[];
  prompt_excerpt: string;
  similarity: number;
}

export interface ThreatIntel {
  rotation_steps: string;
  recent_breaches: { name: string; date: string; summary: string; url: string }[];
  threat_actor_notes: string;
  immediate_actions: string[];
  sources: string[];
}

export interface AgenticNarrative {
  narrative: string;
  trace: { tool: string; args: Record<string, unknown>; result_preview: string }[];
  hops?: number;
  window_hours: number;
}

export interface StatsSummary {
  total_events: number;
  by_decision: Record<string, number>;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  by_destination: Record<string, number>;
  overrides_applied: number;
  window_hours: number;
}

export interface PolicyRule {
  name: string;
  action: LTAction;
  priority: number;
  description: string;
}

// On the server (RSC / route handlers / SSR), fetch must use an absolute URL —
// relative paths don't resolve to anything because Next.js rewrites only apply
// to inbound requests, not outbound fetches. On the client we use /api/* so the
// rewrite layer takes over and the dashboard works behind any reverse proxy.
const API_BASE =
  typeof window === 'undefined'
    ? (process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8001')
    : '/api';

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: 'no-store', ...init });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
}

export async function fetchEvents(opts: { after?: string; limit?: number } = {}) {
  const q = new URLSearchParams();
  if (opts.after) q.set('after', opts.after);
  if (opts.limit) q.set('limit', String(opts.limit));
  const qs = q.toString();
  return getJson<{ events: EventRecord[]; next_cursor: string | null }>(`/events${qs ? `?${qs}` : ''}`);
}

export async function fetchEvent(id: string) {
  return getJson<EventRecord>(`/events/${encodeURIComponent(id)}`);
}

export async function fetchStats(windowHours = 24) {
  return getJson<StatsSummary>(`/stats?window_hours=${windowHours}`);
}

export async function fetchNarrative(windowHours = 24) {
  const r = await fetch(`${API_BASE}/stats/narrative?window_hours=${windowHours}`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`narrative ${r.status}`);
  return r.json() as Promise<{ narrative: string; events_considered: number; window_hours: number }>;
}

export async function fetchRules() {
  return getJson<{ rules: PolicyRule[] }>('/policy/rules');
}

export async function fetchSimilar(eventId: string, k = 5) {
  return getJson<{ event_id: string; neighbors: SimilarNeighbor[]; note?: string }>(
    `/events/${encodeURIComponent(eventId)}/similar?k=${k}`,
  );
}

export async function fetchThreatIntel(eventId: string) {
  const r = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/enrich/threat-intel`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`threat-intel ${r.status}`);
  return r.json() as Promise<{ event_id: string; credential_type: string; threat_intel: ThreatIntel }>;
}

export async function fetchAgenticNarrative(windowHours = 24) {
  const r = await fetch(`${API_BASE}/stats/narrative/agentic?window_hours=${windowHours}`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`agentic ${r.status}`);
  return r.json() as Promise<AgenticNarrative>;
}

export function severityColor(sev: Severity): string {
  switch (sev) {
    case 'critical': return '#dc2626';
    case 'high':     return '#ea580c';
    case 'medium':   return '#ca8a04';
    case 'low':      return '#16a34a';
    default:         return '#64748b';
  }
}

export function decisionColor(d: Decision): string {
  switch (d) {
    case 'block':  return '#dc2626';
    case 'redact': return '#ca8a04';
    case 'allow':  return '#16a34a';
  }
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.round((now - then) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.round(hr / 24);
  return `${d}d ago`;
}
