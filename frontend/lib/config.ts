/**
 * Frontend application configuration.
 * Centralizes environment variable access.
 */

export const config = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    (typeof window !== "undefined" ? "/api/v1" : "http://127.0.0.1:8000/api/v1"),
  appName: "YojanSetu",
  appNameHindi: "योजनसेतु",
  appSubtitleHindi: "राष्ट्रीय एवं राज्य जनकल्याण योजना सेतु (भारत)",
  appTagline: "All-India AI-Powered Public Welfare Discovery & Statutory Eligibility Verification",
} as const;
