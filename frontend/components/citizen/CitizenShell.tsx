"use client";

import React from "react";
import Link from "next/link";
import { LanguageToggle } from "./LanguageToggle";

interface CitizenShellProps {
  children: React.ReactNode;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onLanguageChange: (lang: "hi" | "en") => void;
  onResetSession?: () => void;
  onStartOver?: () => void;
  hasActiveSession?: boolean;
  showStartOver?: boolean;
  isResetting?: boolean;
}

export function CitizenShell({
  children,
  lang,
  language,
  onLanguageChange,
  onResetSession,
  onStartOver,
  hasActiveSession,
  showStartOver,
  isResetting = false,
}: CitizenShellProps) {
  const activeLang = language || lang || "hi";
  const handleReset = onStartOver || onResetSession || (() => {});
  const showResetBtn = showStartOver !== undefined ? showStartOver : Boolean(hasActiveSession);
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Accessible Skip Link */}
      <a
        href="#main-citizen-content"
        className="sr-only focus:not-sr-only focus:absolute focus:p-3 focus:bg-orange-600 focus:text-white focus:z-50"
      >
        {activeLang === "hi" ? "मुख्य सामग्री पर जाएं" : "Skip to main content"}
      </a>

      {/* Top Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 shadow-xs">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-2">
          {/* Logo & Branding */}
          <Link
            href="/citizen"
            className="flex items-center gap-2 group text-left focus:outline-none focus:ring-2 focus:ring-orange-500 rounded-lg p-1"
          >
            <div className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center text-white font-black text-lg shadow-sm group-hover:bg-orange-700 transition-colors">
              JS
            </div>
            <div>
              <div className="font-extrabold text-base sm:text-lg text-slate-900 tracking-tight leading-tight">
                JanSetu
              </div>
              <div className="text-xs text-orange-700 font-medium leading-none">
                {activeLang === "hi"
                  ? "राजस्थान सरकारी योजना सहायक"
                  : "Rajasthan Scheme Assistant"}
              </div>
            </div>
          </Link>

          {/* Controls: Reset + Language */}
          <div className="flex items-center gap-2">
            {showResetBtn && (
              <button
                type="button"
                id="btn-new-search"
                onClick={handleReset}
                disabled={isResetting}
                title={activeLang === "hi" ? "नई खोज शुरू करें" : "Start a new search"}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 rounded-lg border border-slate-300 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <span>🔄</span>
                <span className="hidden xs:inline">
                  {activeLang === "hi" ? "नई खोज" : "New Search"}
                </span>
              </button>
            )}

            <LanguageToggle
              currentLang={activeLang}
              onLanguageChange={onLanguageChange}
            />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main
        id="main-citizen-content"
        className="flex-1 max-w-4xl w-full mx-auto px-4 py-6 sm:py-8"
      >
        {children}
      </main>

      {/* Trustworthy Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 mt-auto">
        <div className="max-w-4xl mx-auto px-4 text-center text-xs text-slate-500 space-y-1">
          <p className="font-medium text-slate-600">
            {activeLang === "hi"
              ? "जनसेतु केवल मार्गदर्शन एवं आधिकारिक सूचना उपलब्ध कराता है। यह सीधे आवेदन जमा नहीं करता।"
              : "JanSetu provides guidance and verified official information. It does not submit applications directly."}
          </p>
          <p className="text-slate-400">
            {activeLang === "hi"
              ? "गोपनीयता सुरक्षित • सत्र डेटा केवल अस्थायी मेमोरी में रखा जाता है"
              : "Privacy protected • Session facts are stored in temporary RAM only"}
          </p>
        </div>
      </footer>
    </div>
  );
}

export default CitizenShell;
