import type { NextConfig } from "next";

const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
  experimental: {
    // Unsealing an envelope takes 10 to 20 seconds and a first practice run downloads about 70 MB;
    // the /api proxy's default 30-second limit could cut either off on a slow laptop.
    proxyTimeout: 180_000,
  },
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
};

export default nextConfig;
