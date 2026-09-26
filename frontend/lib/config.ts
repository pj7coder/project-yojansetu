/**
 * Frontend application configuration.
 * Centralizes environment variable access.
 */

function resolveApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "localhost";
    const protocol = window.location.protocol || "http:";
    return `${protocol}//${host}:8000/api/v1`;
  }
  return "http://localhost:8000/api/v1";
}

export const config = {
  get apiBaseUrl(): string {
    return resolveApiBaseUrl();
  },
  appName: "YojanSetu",
  appNameHindi: "योजनसेतु",
  appSubtitleHindi: "राष्ट्रीय एवं राज्य जनकल्याण योजना सेतु (भारत)",
  appTagline: "All-India AI-Powered Public Welfare Discovery & Statutory Eligibility Verification",
} as const;
