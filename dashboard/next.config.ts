import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  // Tailscale IPs the dev dashboard is reached from. 100.92.127.1 is lg2025
  // itself (the host serving this app) — omitting it breaks HMR and Turbopack
  // client hydration for every visitor. 100.100.199.127 is p330.
  allowedDevOrigins: [
    "100.92.127.1",
    "100.100.199.127"
  ],
};

export default nextConfig;
