import type { NextConfig } from "next";

// Baseline security headers applied to every response. These are the
// non-negotiable, framework-safe hardening headers — none of them depend on
// how the app renders, so they can't break hydration, GSAP, or HMR.
const securityHeaders = [
  // Clickjacking protection. frame-ancestors in the CSP below is the modern
  // equivalent; X-Frame-Options is kept for older browsers.
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  // Stop browsers from MIME-sniffing a response away from its declared type.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Send only the origin (not the full path) on cross-origin navigations.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Lock down powerful browser features we never use.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  // HSTS is ignored by browsers over plain HTTP (as on the Tailscale IPs), so
  // it's harmless in dev and takes effect the moment the dashboard is served
  // over TLS. No preload/includeSubDomains until that's the real deployment.
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
];

// Content-Security-Policy. This app relies on Next.js inline hydration scripts,
// GSAP, Tailwind's injected styles, and (in dev) Turbopack HMR over websockets
// to the Tailscale origins. A nonce-based strict CSP would require middleware
// and is a separate hardening pass; until then this policy keeps the directives
// that add real protection without breaking anything — frame-ancestors
// (clickjacking) and object-src/base-uri lockdown — while leaving
// script/style/connect permissive enough for the app to run.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  // 'self' + ws/wss covers same-origin API calls and Turbopack HMR sockets on
  // the Tailscale hostnames the dashboard is reached from.
  "connect-src 'self' ws: wss:",
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'self'",
].join("; ");

const nextConfig: NextConfig = {
  transpilePackages: ["gsap", "@gsap/react"],
  // Suppress the X-Powered-By: Next.js fingerprint.
  poweredByHeader: false,
  // Tailscale IPs the dev dashboard is reached from. 100.92.127.1 is lg2025
  // itself (the host serving this app) — omitting it breaks HMR and Turbopack
  // client hydration for every visitor. 100.100.199.127 is p330.
  allowedDevOrigins: [
    "100.92.127.1",
    "100.100.199.127"
  ],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          ...securityHeaders,
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

export default nextConfig;
