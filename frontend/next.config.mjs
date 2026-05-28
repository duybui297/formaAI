/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  // D-20: Turbopack is default in Next.js 16 (--turbopack flag in dev script)
  // No webpack config — Turbopack handles bundling
  async rewrites() {
    return [
      {
        // Proxy /api/* to FastAPI backend (avoids CORS in dev)
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://api:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
