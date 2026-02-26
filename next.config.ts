import type { NextConfig } from "next";

const securityHeaders = [
  // Prevent browsers from guessing MIME types
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  // Block clickjacking via iframes from other origins
  {
    key: "X-Frame-Options",
    value: "SAMEORIGIN",
  },
  // Enforce HTTPS for 2 years (only applies when served over HTTPS)
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  // Minimal referrer info on cross-origin navigations
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  // Disable browser features not used by this app
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  // Prevent IE from executing downloads in the site's context
  {
    key: "X-Download-Options",
    value: "noopen",
  },
  // Disable cross-origin isolation for now; enable when using SharedArrayBuffer
  // { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // TODO: Add Content-Security-Policy once external asset inventory is confirmed.
  // Current app uses no external CDNs; a strict self-only policy can be added here:
  // {
  //   key: "Content-Security-Policy",
  //   value: [
  //     "default-src 'self'",
  //     "script-src 'self' 'unsafe-inline'",   // remove unsafe-inline when nonce/hash is wired
  //     "style-src 'self' 'unsafe-inline'",
  //     "img-src 'self' data: blob:",
  //     "font-src 'self'",
  //     "connect-src 'self'",
  //     "frame-ancestors 'self'",
  //     "base-uri 'self'",
  //     "form-action 'self'",
  //   ].join("; "),
  // },
];

const nextConfig: NextConfig = {
  //  output: "export",
  //  basePath: "/Katala",
  images: {
    unoptimized: true,
  },
  async headers() {
    return [
      {
        // Apply security headers to all routes
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
