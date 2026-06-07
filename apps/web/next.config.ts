import type { NextConfig } from "next";

const apiBaseUrl = process.env.CREATOR_SCOUT_API_URL ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBaseUrl}/v1/:path*`,
      },
      {
        source: "/api/health",
        destination: `${apiBaseUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
