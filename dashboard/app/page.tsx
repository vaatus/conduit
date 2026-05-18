// SPDX-License-Identifier: MIT
import Link from 'next/link';
import { Card, CardBody, CardHeader } from '@/components/Card';
import { EventFeed } from '@/components/EventFeed';
import { StatsPanel } from '@/components/StatsPanel';
import { NarrativeCard } from '@/components/NarrativeCard';
import { AgenticNarrativeCard } from '@/components/AgenticNarrativeCard';

export default function HomePage() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Overview</h1>
        <p className="text-sm text-ink-500 mt-1">
          Live audit feed of every prompt your employees attempted to send to a public LLM in the last 24 hours.
          Lobster Trap inspects; Gemini classifies and sanitizes.
        </p>
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        <NarrativeCard />
        <AgenticNarrativeCard />
      </div>

      <StatsPanel />

      <Card>
        <CardHeader
          title="Recent events"
          hint="Polls every 2.5s"
          action={
            <Link
              href="/events"
              className="text-xs font-medium px-3 py-1.5 rounded-md text-ink-900 hover:bg-ink-100"
            >
              View all →
            </Link>
          }
        />
        <CardBody>
          <EventFeed limit={20} />
        </CardBody>
      </Card>
    </div>
  );
}
