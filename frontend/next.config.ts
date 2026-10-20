import type { NextConfig } from "next";
const proxyLimitMb = Number(process.env.PROXY_BODY_LIMIT_MB || 25);
if (!Number.isFinite(proxyLimitMb) || proxyLimitMb < 1)
  throw new Error("PROXY_BODY_LIMIT_MB must be a positive number");
const config: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
  experimental: {
    proxyClientMaxBodySize: proxyLimitMb * 1024 * 1024,
  },
};
export default config;
