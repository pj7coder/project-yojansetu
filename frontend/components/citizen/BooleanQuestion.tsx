"use client";

import React from "react";
import { CitizenQuestionDisplay } from "../../types/citizen";

interface BooleanQuestionProps {
  question: CitizenQuestionDisplay;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onSubmit: (value: boolean) => void;
  onSkip?: () => void;
  onDecline: () => void;
  isSubmitting: boolean;
}

export function BooleanQuestion({
  question,
  lang: propLang,
  language,
  onSubmit,
  onSkip,
  onDecline,
  isSubmitting,
}: BooleanQuestionProps) {
  const lang = language || propLang || "hi";
  return (
    <div className="space-y-4">
      <div className="space-y-1 text-left">
        <label className="block text-sm font-semibold text-slate-700">
          {lang === "hi" ? question.display_name_hi : question.display_name_en}
        </label>
        {question.help_text_hi && lang === "hi" && (
          <p className="text-xs text-slate-500">{question.help_text_hi}</p>
        )}
        {question.help_text_en && lang === "en" && (
          <p className="text-xs text-slate-500">{question.help_text_en}</p>
        )}
      </div>

      {/* Main Choice Cards: Yes / No */}
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          id="btn-bool-yes"
          onClick={() => onSubmit(true)}
          disabled={isSubmitting}
          className="min-h-[56px] p-4 rounded-xl border-2 border-emerald-200 bg-emerald-50/60 hover:bg-emerald-100/80 hover:border-emerald-400 active:scale-[0.98] text-emerald-950 flex flex-col items-center justify-center transition-all disabled:opacity-50"
        >
          <span className="text-base font-extrabold">
            {lang === "hi" ? "हाँ" : "Yes"}
          </span>
          <span className="text-xs text-emerald-700 font-medium">
            {lang === "hi" ? "Yes" : "हाँ"}
          </span>
        </button>

        <button
          type="button"
          id="btn-bool-no"
          onClick={() => onSubmit(false)}
          disabled={isSubmitting}
          className="min-h-[56px] p-4 rounded-xl border-2 border-slate-200 bg-white hover:bg-slate-100 hover:border-slate-300 active:scale-[0.98] text-slate-800 flex flex-col items-center justify-center transition-all disabled:opacity-50"
        >
          <span className="text-base font-extrabold">
            {lang === "hi" ? "नहीं" : "No"}
          </span>
          <span className="text-xs text-slate-500 font-medium">
            {lang === "hi" ? "No" : "नहीं"}
          </span>
        </button>
      </div>

      {/* Auxiliary actions: Don't know / Prefer not to say */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
        <button
          type="button"
          id="btn-bool-unknown"
          onClick={onSkip}
          disabled={isSubmitting}
          className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
        >
          ❓ {lang === "hi" ? "पता नहीं" : "Don't know"}
        </button>

        {question.allow_decline && (
          <button
            type="button"
            id="btn-bool-decline"
            onClick={onDecline}
            disabled={isSubmitting}
            className="px-3.5 py-2 text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
          >
            {lang === "hi" ? "बताने में असुविधा है" : "Prefer not to say"}
          </button>
        )}
      </div>
    </div>
  );
}

export default BooleanQuestion;
