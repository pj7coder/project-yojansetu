/**
 * Frontend application configuration.
 * Centralizes environment variable access.
 */

export const config = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
  appName: "JanSetu",
  appNameHindi: "जनसेतु",
  appSubtitleHindi: "राजस्थान सरकारी योजना सहायता",
  appTagline: "Offline-first vernacular government-scheme discovery assistant for Rajasthan",
} as const;
