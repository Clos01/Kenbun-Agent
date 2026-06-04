/**
 * Kenbun Dashboard Sovereign Configuration
 * Centralizes all environment variables and constants.
 *
 * Portable Design: The API URL is auto-detected from the browser's
 * current hostname so this works on localhost, LAN, Tailscale, etc.
 * Users only need to set NEXT_PUBLIC_API_PORT in .env if non-default.
 */

export const CONFIG = {
  get API_BASE() {
    return '/api_proxy';
  },
  IS_PRODUCTION: process.env.NODE_ENV === "production",
  SYSTEM_VERSION: "1.7.7-ARTISAN",
  RETRY_ATTEMPTS: 3,
  POLLING_INTERVAL: 5000,
};


