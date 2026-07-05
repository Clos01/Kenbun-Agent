import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  // Dynamic origins to avoid hardcoded IPs (Technical Debt resolved)
  allowedDevOrigins: [
    ...(process.env.TAILSCALE_IP ? [
      process.env.TAILSCALE_IP,
      `${process.env.TAILSCALE_IP}:3000`,
      `http://${process.env.TAILSCALE_IP}:3000`
    ] : []),
    ...(process.env.PC_IP_ADDRESS ? [
      process.env.PC_IP_ADDRESS,
      `${process.env.PC_IP_ADDRESS}:3000`,
      `http://${process.env.PC_IP_ADDRESS}:3000`
    ] : [])
  ],
};

export default nextConfig;
