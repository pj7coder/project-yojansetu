"use client";

import React from "react";
import { SchemeCitation } from "@/types/agent";

interface CitationDrawerProps {
  language: "hi" | "en";
  citation: SchemeCitation | null;
  onClose: () => void;
}

export function CitationDrawer({ language, citation, onClose }: CitationDrawerProps) {
  const isHi = language === "hi";

  if (!citation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-amber-300 max-w-xl w-full overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header with Rajasthan Emblem Styling */}
        <div className="bg-linear-to-r from-amber-700 via-orange-700 to-amber-800 text-white p-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-lg">
              🏛️
            </div>
            <div>
              <div className="text-[10px] font-bold tracking-widest uppercase text-amber-200">
                {isHi ? "राजस्थान सरकार • राजपत्र साक्ष्य" : "Govt of Rajasthan • Gazette Evidence"}
              </div>
              <h3 className="text-sm font-extrabold tracking-tight">
                {citation.title || (isHi ? "आधिकारिक परिपत्र साक्ष्य" : "Official Circular Clause")}
              </h3>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center font-bold text-sm transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Verification Ribbon */}
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-amber-900">
          <div className="flex items-center gap-2 font-mono">
            <span>🔖</span>
            <span>{citation.citation_tag}</span>
          </div>
          <span className="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded border border-emerald-300">
            {isHi ? "सत्यापित खंड" : "Ground Truth"}
          </span>
        </div>

        {/* Body Excerpt */}
        <div className="p-5 overflow-y-auto space-y-4 text-slate-800 text-xs sm:text-sm leading-relaxed">
          <div className="bg-slate-50 border-l-4 border-amber-500 p-4 rounded-r-xl font-serif text-slate-700 shadow-2xs">
            <div className="text-[11px] font-bold text-slate-400 uppercase font-sans mb-1">
              {isHi ? "राजपत्रित अधिसूचना से उद्धरण:" : "Verbatim Gazette Notification Extract:"}
            </div>
            <p className="whitespace-pre-wrap leading-relaxed">
              "{citation.snippet}"
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 flex items-start gap-2.5 text-blue-900 text-xs">
            <span className="text-base">🛡️</span>
            <div>
              <div className="font-bold">
                {isHi ? "शून्य-भ्रांति वास्तुकला (Zero-Hallucination Proof)" : "Zero-Hallucination Architecture"}
              </div>
              <p className="text-[11px] text-blue-800 mt-0.5">
                {isHi
                  ? "योजनसेतु में कोई भी पेंशन राशि या पात्रता शर्त भाषा मॉडल द्वारा अनुमानित नहीं है। सभी खंड सीधे राजस्थान सरकार के गजट से उद्धृत हैं।"
                  : "Every benefit slab and condition is anchored directly to this gazetted notification clause via hybrid BM25 + dense vector RAG."}
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">
            Page: {citation.page || "1"}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition-colors cursor-pointer"
          >
            {isHi ? "बंद करें" : "Close"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CitationDrawer;
