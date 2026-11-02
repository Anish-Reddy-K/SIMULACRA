import type { NextConfig } from "next";

const API_ORIGIN = process.env.SIMULACRA_API_ORIGIN ?? "http://127.0.0.1:8765";
const isDev = process.env.NODE_ENV === "development";

// Production is a static export served by the FastAPI process (ADR-0002).
// In dev, proxy /api to the API so the browser sees one origin either way.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
  ...(isDev && {
    async rewrites() {
      return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
    },
  }),
};

export default nextConfig;
