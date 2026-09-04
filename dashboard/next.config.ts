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
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://esm.sh",
  "style-src 'self' 'unsafe-inline' https://esm.sh",
  "img-src 'self' data: blob:",
  "font-src 'self' data: https://esm.sh",
  // 'self' + ws/wss covers same-origin API calls and Turbopack HMR sockets on
  // the Tailscale hostnames the dashboard is reached from.
  "connect-src 'self' ws: wss: https://esm.sh",
  "object-src 'none'",
  "base-uri 'self'",
  "frame-src *",
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
    "100.104.211.61",
    "100.92.127.1",
    "100.100.199.127",
    "lg2025.tailbe4852.ts.net",
    "kenbun.lan"
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
      {
        // Make the document revalidate instead of letting the browser guess.
        //
        // Next gives a statically prerendered page `s-maxage=31536000` — a year,
        // addressed to a SHARED cache, on the assumption a CDN sits in front and
        // gets purged on deploy. This dashboard is served straight off the
        // container over Tailscale: there is no CDN, so the browser is the only
        // cache, and browsers ignore `s-maxage`. With no `max-age`, no `Expires`
        // and no `no-cache`, the document falls into HEURISTIC freshness, where
        // the browser invents a lifetime from Last-Modified.
        //
        // That is what made frontend changes look like they had not deployed. The
        // stale document still references the previous build's asset names, and
        // those names are content-hashed and served `immutable`, so the browser
        // reuses the old JS quite correctly — the wrong thing is the document
        // telling it to. A normal reload showed the old build; only a
        // cache-bypassing hard reload showed the new one.
        //
        // `no-cache` means "store it, but revalidate before use" — not "do not
        // store". Unchanged documents come back as a 304, so this costs one
        // conditional request per navigation and makes a redeploy visible on the
        // next load.
        //
        // /_next/static is excluded: those filenames contain a content hash, so
        // caching them for a year is correct, and Next does not permit
        // overriding their header anyway.
        source: "/:path((?!_next/static|_next/image).*)",
        headers: [{ key: "Cache-Control", value: "no-cache" }],
      },
    ];
  },
};

export default nextConfig;
