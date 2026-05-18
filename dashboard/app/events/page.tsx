// SPDX-License-Identifier: MIT
import { Card, CardBody, CardHeader } from '@/components/Card';
import { EventFeed } from '@/components/EventFeed';

export default function EventsPage() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Events</h1>
        <p className="text-sm text-ink-500 mt-1">Every paste, sanitization, and block — chronological, drill-into-able.</p>
      </section>
      <Card>
        <CardHeader title="Live event stream" hint="Polls every 2.5s · max 100 rows" />
        <CardBody><EventFeed limit={100} /></CardBody>
      </Card>
    </div>
  );
}
