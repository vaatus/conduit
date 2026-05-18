// SPDX-License-Identifier: MIT
import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Conduit — Shadow AI Governance',
  description: 'Inspects every prompt headed to a public LLM. Powered by Veea Lobster Trap + Gemini.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <header className="border-b bg-white">
          <div className="mx-auto max-w-7xl px-6 py-4 flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-ink-900 text-white text-sm font-semibold">C</span>
              <span className="font-semibold tracking-tight">Conduit</span>
              <span className="text-xs text-ink-500 hidden sm:inline">Shadow-AI Governance</span>
            </Link>
            <nav className="ml-auto flex items-center gap-1 text-sm">
              <NavLink href="/">Overview</NavLink>
              <NavLink href="/events">Events</NavLink>
              <NavLink href="/tests">Tests</NavLink>
              <NavLink href="/policy">Policy</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
        <footer className="border-t bg-white mt-12">
          <div className="mx-auto max-w-7xl px-6 py-4 text-xs text-ink-500 flex justify-between">
            <span>Conduit · MIT · Track 1 — Agent Security &amp; AI Governance</span>
            <span>Veea Lobster Trap + Gemini 2.5</span>
          </div>
        </footer>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 rounded-md text-ink-700 hover:bg-ink-100 hover:text-ink-900 transition"
    >
      {children}
    </Link>
  );
}
