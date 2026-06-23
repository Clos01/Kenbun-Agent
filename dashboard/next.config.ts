import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  // @ts-ignore
  allowedDevOrigins: [
    "100.120.241.65", 
    "100.120.241.65:3000", 
    "http://100.120.241.65:3000",
    "100.104.211.61",
    "100.104.211.61:3000",
    "http://100.104.211.61:3000",
    "100.91.110.91",
    "100.91.110.91:3000",
    "http://100.91.110.91:3000",
    "100.67.28.126",
    "100.67.28.126:3000",
    "http://100.67.28.126:3000"
  ],
};

export default nextConfig;
