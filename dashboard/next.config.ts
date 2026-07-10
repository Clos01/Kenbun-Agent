import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  // Hardcode the tailscale IP so HMR websocket works across the VPN without relying on missing ENV vars
  allowedDevOrigins: [
    "100.100.199.127"
  ],
};

export default nextConfig;
