import type { NextConfig } from "next";

function stripTrailingSlash(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

const scannerApiInternalUrl = stripTrailingSlash(
  process.env.SCANNER_API_INTERNAL_URL ?? process.env.SCANNER_API_BASE_URL ?? "http://127.0.0.1:8000",
);

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: "standalone",
  env: {
    NEXT_PUBLIC_SCANNER_API_BASE_URL: process.env.NEXT_PUBLIC_SCANNER_API_BASE_URL ?? "/scanner-api",
    NEXT_PUBLIC_SCANNER_API_MODE: process.env.NEXT_PUBLIC_SCANNER_API_MODE ?? process.env.SCANNER_API_MODE ?? "live",
  },
  async rewrites() {
    return [
      {
        source: "/scanner-api/:path*",
        destination: `${scannerApiInternalUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
