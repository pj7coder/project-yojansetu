"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getHealth, getDatabaseHealth } from "../lib/api";
import { HealthState } from "../types/health";

export default function HomePage() {
  const [lang, setLang] = useState<"hi" | "en">("hi");
  const [healthState, setHealthState] = useState<HealthState>({
    status: "checking",
    data: null,
    errorMessage: null,
    latencyMs: null,
    lastChecked: null,
    databaseStatus: "checking",
    databaseMessage: null,
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkConnection = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const { data, latencyMs } = await getHealth(4000);
      let dbStatus: "connected" | "unavailable" = "unavailable";
      let dbMsg: string | null = null;
      try {
        const dbResult = await getDatabaseHealth(4000);
        if (dbResult && dbResult.status === "ok") {
          dbStatus = "connected";
        }
      } catch (dbErr) {
        dbMsg = dbErr instanceof Error ? dbErr.message : "DB check failed";
      }

      setHealthState({
        status: "connected",
        data,
        errorMessage: null,
        latencyMs,
        lastChecked: new Date(),
        databaseStatus: dbStatus,
        databaseMessage: dbMsg,
      });
    } catch {
      setHealthState({
        status: "unavailable",
        data: null,
        errorMessage: "Backend offline",
        latencyMs: null,
        lastChecked: new Date(),
        databaseStatus: "unavailable",
        databaseMessage: "Backend unavailable",
      });
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  const isHi = lang === "hi";

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      {/* Top Navigation Bar */}
      <header className="w-full bg-white/95 backdrop-blur border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-600 text-white flex items-center justify-center font-black text-xl shadow-md shadow-orange-600/20">
              JS
            </div>
            <div>
              <div className="font-black text-lg tracking-tight text-slate-900 leading-tight">
                JANSETU
              </div>
              <div className="text-xs text-orange-700 font-semibold leading-tight">
                {isHi ? "जनसेतु • राजस्थान सरकार" : "Government of Rajasthan"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* System Status Pill */}
            <button
              onClick={checkConnection}
              disabled={isRefreshing}
              title="Click to re-check backend status"
              className="hidden sm:inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  healthState.status === "connected"
                    ? "bg-emerald-500 animate-pulse"
                    : healthState.status === "checking"
                    ? "bg-amber-400"
                    : "bg-rose-500"
                }`}
              />
              <span>
                {healthState.status === "connected"
                  ? isHi
                    ? "सिस्टम सक्रिय"
                    : "System Online"
                  : healthState.status === "checking"
                  ? isHi
                    ? "जाँच जारी..."
                    : "Checking..."
                  : isHi
                  ? "ऑफ़लाइन"
                  : "Offline"}
              </span>
            </button>

            {/* Language Toggle */}
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-bold">
              <button
                type="button"
                onClick={() => setLang("hi")}
                className={`px-3 py-1 rounded-md transition-all ${
                  isHi
                    ? "bg-white text-orange-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                हिन्दी
              </button>
              <button
                type="button"
                onClick={() => setLang("en")}
                className={`px-3 py-1 rounded-md transition-all ${
                  !isHi
                    ? "bg-white text-orange-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                English
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Hero & Portals */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-10">
        {/* Hero Section */}
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-orange-100 text-orange-800 border border-orange-200 shadow-xs">
            <span>🏛️</span>
            <span>
              {isHi
                ? "राजस्थान सरकारी जन-कल्याण योजना पोर्टल"
                : "Rajasthan Welfare Scheme Discovery Platform"}
            </span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight">
            {isHi ? (
              <>
                अपनी पात्रता जानें,{" "}
                <span className="text-orange-600">योजनाओं का लाभ पाएँ</span>
              </>
            ) : (
              <>
                Discover Your Eligibility for{" "}
                <span className="text-orange-600">Government Schemes</span>
              </>
            )}
          </h1>

          <p className="text-base sm:text-lg text-slate-600 font-medium leading-relaxed">
            {isHi
              ? "बिना किसी सरकारी कार्यालय जाए, बोलकर या लिखकर सरल हिंदी में अपनी और अपने परिवार की पात्र योजनाओं की सटीक जानकारी प्राप्त करें।"
              : "An offline-first, vernacular assistant helping rural, elderly, and Hindi-first citizens discover welfare schemes through voice or text."}
          </p>
        </div>

        {/* Two Main Gateway Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 1. Citizen Welfare Discovery Gateway */}
          <div className="bg-gradient-to-br from-orange-500 to-amber-600 text-white rounded-3xl p-7 sm:p-9 flex flex-col justify-between shadow-xl shadow-orange-500/15 relative overflow-hidden group hover:shadow-2xl transition-all">
            <div className="space-y-4 relative z-10">
              <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center text-3xl shadow-inner">
                🔍
              </div>
              <div className="space-y-1">
                <span className="text-xs font-black uppercase tracking-wider text-orange-200">
                  {isHi ? "नागरिक सेवा केंद्र" : "Citizen Welfare Portal"}
                </span>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {isHi ? "योजनाएँ खोजें" : "Find Eligible Schemes"}
                </h2>
              </div>
              <p className="text-sm sm:text-base text-orange-100 leading-relaxed font-normal">
                {isHi
                  ? "बोलकर या लिखकर बताएं कि आपको किस प्रकार की सहायता चाहिए। हमारा सहायक आपसे 1-2 सरल प्रश्न पूछकर तुरंत सही योजना बताएगा।"
                  : "State your need in text or voice. The assistant asks minimal guided questions to determine your eligibility with zero hallucinations."}
              </p>

              {/* Highlights */}
              <div className="grid grid-cols-2 gap-2 pt-2 text-xs font-semibold text-orange-100">
                <div className="flex items-center gap-2">
                  <span>✓</span>
                  <span>{isHi ? "आवाज व टेक्स्ट दोनों" : "Voice & Text Input"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>✓</span>
                  <span>{isHi ? "100% गोपनीय व सुरक्षित" : "100% Private (No DB Storage)"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>✓</span>
                  <span>{isHi ? "सरल मारवाड़ी व हिंदी" : "Vernacular Hindi & Dialects"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span>✓</span>
                  <span>{isHi ? "आवेदन व दस्तावेज़ सूची" : "Application & Document Checklist"}</span>
                </div>
              </div>
            </div>

            <div className="pt-6 relative z-10">
              <Link
                href="/citizen"
                className="w-full inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-white text-orange-700 font-extrabold text-base shadow-md hover:bg-orange-50 active:scale-98 transition-all"
              >
                <span>{isHi ? "नागरिक पोर्टल खोलें" : "Launch Citizen Assistant"}</span>
                <span className="text-lg">→</span>
              </Link>
            </div>
          </div>

          {/* 2. Admin Operations Center Gateway */}
          <div className="bg-slate-900 text-white rounded-3xl p-7 sm:p-9 flex flex-col justify-between shadow-xl shadow-slate-900/10 relative overflow-hidden group hover:shadow-2xl transition-all border border-slate-800">
            <div className="space-y-4 relative z-10">
              <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center text-3xl shadow-inner border border-white/10">
                ⚙️
              </div>
              <div className="space-y-1">
                <span className="text-xs font-black uppercase tracking-wider text-slate-400">
                  {isHi ? "प्रशासनिक नियंत्रण केंद्र" : "Admin Operations Center"}
                </span>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {isHi ? "समीक्षा व संचालन" : "Review & Operations"}
                </h2>
              </div>
              <p className="text-sm sm:text-base text-slate-300 leading-relaxed font-normal">
                {isHi
                  ? "सरकारी पीडीएफ अपलोड करें, एआई द्वारा निकाले गए तथ्यों की स्रोत से तुलना करें और आधिकारिक योजनाओं को सत्यापित करें।"
                  : "Upload government PDF guidelines, verify extracted facts side-by-side with official documents, and manage scheme versions."}
              </p>

              {/* Highlights */}
              <div className="grid grid-cols-2 gap-2 pt-2 text-xs font-semibold text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{isHi ? "विभाजित स्क्रीन समीक्षा" : "Split-Screen PDF Review"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{isHi ? "संशोधन व संस्करण" : "Amendments & Corrigenda"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{isHi ? "सरकारी पोर्टल मॉनिटरिंग" : "Portal Change Monitoring"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{isHi ? "10-चरणीय पाइपलाइन कतार" : "10-Stage Processing Queue"}</span>
                </div>
              </div>
            </div>

            <div className="pt-6 relative z-10">
              <Link
                href="/admin"
                className="w-full inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-extrabold text-base border border-slate-700 shadow-md active:scale-98 transition-all"
              >
                <span>{isHi ? "एडमिन डैशबोर्ड खोलें" : "Open Admin Control Center"}</span>
                <span className="text-lg">→</span>
              </Link>
            </div>
          </div>
        </div>

        {/* Quick Topic Chips */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4 text-center">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
            {isHi ? "प्रमुख कल्याणकारी श्रेणियां" : "Popular Welfare Categories"}
          </h3>
          <div className="flex flex-wrap items-center justify-center gap-3">
            {[
              { icon: "🌾", hi: "किसान सहायता", en: "Farmer Assistance" },
              { icon: "👴", hi: "वृद्धावस्था पेंशन", en: "Old Age Pension" },
              { icon: "🎓", hi: "छात्रवृत्ति योजना", en: "Student Scholarship" },
              { icon: "🏥", hi: "स्वास्थ्य व इलाज", en: "Health Insurance" },
              { icon: "👩", hi: "महिला कल्याण", en: "Women Welfare" },
              { icon: "💼", hi: "स्वरोजगार लोन", en: "Self Employment" },
            ].map((cat, i) => (
              <Link
                key={i}
                href="/citizen"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 hover:bg-orange-50 hover:text-orange-700 hover:border-orange-300 text-slate-700 text-sm font-bold border border-slate-200 transition-all active:scale-95"
              >
                <span>{cat.icon}</span>
                <span>{isHi ? cat.hi : cat.en}</span>
              </Link>
            ))}
          </div>
        </div>
      </main>

      {/* Accessible Footer */}
      <footer className="w-full bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700">JanSetu (जनसेतु)</span>
            <span>•</span>
            <span>{isHi ? "राजस्थान सरकार कल्याण पोर्टल" : "Rajasthan Welfare Discovery"}</span>
          </div>
          <div className="flex items-center gap-4 text-slate-500">
            <Link href="/citizen" className="hover:text-orange-600 transition">
              {isHi ? "नागरिक पोर्टल" : "Citizen Portal"}
            </Link>
            <span>•</span>
            <Link href="/admin" className="hover:text-orange-600 transition">
              {isHi ? "एडमिन डैशबोर्ड" : "Admin Dashboard"}
            </Link>
            <span>•</span>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="hover:text-orange-600 transition"
            >
              API Docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
