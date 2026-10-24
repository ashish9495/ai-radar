import type { NextConfig } from "next";

// GitHub Pages serves project sites under /<repo>. Set NEXT_PUBLIC_BASE_PATH="/ai-radar" in CI
// (or "" for a user/organisation site or custom domain).
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const config: NextConfig = {
  output: "export",           // fully static: no SSR, API routes or server actions
  basePath,
  assetPrefix: basePath || undefined,
  trailingSlash: true,        // /news/ -> /news/index.html, which GitHub Pages serves directly
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
};

export default config;
