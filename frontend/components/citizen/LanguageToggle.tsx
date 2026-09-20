"use client";

import React from "react";

interface LanguageToggleProps {
  currentLang: "hi" | "en";
  onLanguageChange: (lang: "hi" | "en") => void;
}

export function LanguageToggle({
  currentLang,
  onLanguageChange,
}: LanguageToggleProps) {
  return (
    <div
      role="group"
      aria-label="Language Selector"
      className="inline-flex items-center bg-slate-100 p-1 rounded-full border border-slate-200 shadow-sm"
    >
      <button
        type="button"
        id="lang-toggle-hi"
        onClick={() => onLanguageChange("hi")}
        aria-pressed={currentLang === "hi"}
        className={`px-3 py-1 text-xs sm:text-sm font-semibold rounded-full transition-all duration-200 ${
          currentLang === "hi"
            ? "bg-orange-600 text-white shadow-sm"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        हिंदी
      </button>
      <button
        type="button"
        id="lang-toggle-en"
        onClick={() => onLanguageChange("en")}
        aria-pressed={currentLang === "en"}
        className={`px-3 py-1 text-xs sm:text-sm font-semibold rounded-full transition-all duration-200 ${
          currentLang === "en"
            ? "bg-orange-600 text-white shadow-sm"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        English
      </button>
    </div>
  );
}

export default LanguageToggle;
