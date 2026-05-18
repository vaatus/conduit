// SPDX-License-Identifier: MIT
import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="py-20 text-center">
      <h1 className="text-2xl font-semibold text-ink-900">Not found</h1>
      <p className="text-sm text-ink-500 mt-2">That page or event id doesn't exist.</p>
      <Link href="/" className="inline-block mt-6 text-sm font-medium text-ink-900 underline">← back to overview</Link>
    </div>
  );
}
