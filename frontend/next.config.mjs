/** @type {import('next').NextConfig} */
const nextConfig = {
  // Hide the Next.js dev tools badge (bottom-corner logo) in dev
  devIndicators: false,
  images: {
    unoptimized: true,
  },
  // D-20: Turbopack is default in Next.js 16 (--turbopack flag in dev script)
  // No webpack config — Turbopack handles bundling
  async rewrites() {
    return [
      {
        // Proxy /api/* to FastAPI backend (avoids CORS in dev).
        // Forward the full /api prefix unchanged so backend receives /api/v1/*.
        // Backend mounts all routes at /api/v1 (see backend/src/app/main.py).
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://api:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
