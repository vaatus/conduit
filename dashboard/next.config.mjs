// SPDX-License-Identifier: MIT
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API || 'http://localhost:8001';
    // Catch-all proxy: every /api/* request on the dashboard goes straight to
    // the FastAPI backend. Covers nested paths like /api/events/{id}/similar,
    // /api/events/{id}/enrich/threat-intel, /api/stats/narrative/agentic, etc.
    return [
      { source: '/api/:path*', destination: `${api}/:path*` },
    ];
  },
};

export default nextConfig;
