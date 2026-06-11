import type { NextConfig } from "next";

const allowedOrigins = ["localhost", "127.0.0.1"];
if (process.env.ASSEMBLY_PC_IP) {
  allowedOrigins.push(process.env.ASSEMBLY_PC_IP);
}

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  allowedDevOrigins: allowedOrigins,
};

export default nextConfig;
