"use client";

import React, { useState } from "react";
import { CitizenQuestionDisplay } from "../../types/citizen";

interface NumberQuestionProps {
  question: CitizenQuestionDisplay;
  lang: "hi" | "en";
  onSubmit: (value: number) => void;
  onDecline: () => void;
  isSubmitting: boolean;
}

export function NumberQuestion({
  question,
  lang,
  onSubmit,
  onDecline,
  isSubmitting,
}: NumberQuestionProps) {
  const [val, setVal] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const unit = lang === "hi" ? question.unit_hi : question.unit_en;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    const num = parseFloat(val.trim());
    if (isNaN(num)) {
      setErrorMsg(
        lang === "hi"
          ? "कृपया मान्य संख्या दर्ज करें"
          : "Please enter a valid numeric value"
      );
      return;
    }

    if (num < 0) {
      setErrorMsg(
        lang === "hi"
          ? "ऋणात्मक मान मान्य नहीं है"
          : "Negative values are not permitted"
      );
      return;
    }

    // Specific reasonable guardrails
    if (question.field === "age" && (num < 0 || num > 125)) {
      setErrorMsg(
        lang === "hi"
          ? "कृपया 0 से 120 के बीच मान्य आयु दर्ज करें"
          : "Please enter a valid age between 0 and 120"
      );
      return;
    }

    setErrorMsg(null);
    onSubmit(num);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label
          htmlFor={`input-${question.field}`}
          className="block text-sm font-semibold text-slate-700 text-left"
        >
          {lang === "hi" ? question.display_name_hi : question.display_name_en}
        </label>

        <div className="relative flex items-center rounded-xl shadow-inner bg-slate-50 border border-slate-300 focus-within:border-orange-500 focus-within:ring-2 focus-within:ring-orange-500/20 transition-all">
          <input
            id={`input-${question.field}`}
            type="number"
            value={val}
            onChange={(e) => {
              setVal(e.target.value);
              setErrorMsg(null);
            }}
            disabled={isSubmitting}
            placeholder={lang === "hi" ? "यहाँ दर्ज करें…" : "Enter value…"}
            className="w-full px-4 py-3 text-lg font-bold text-slate-900 bg-transparent focus:outline-none disabled:opacity-50"
            autoFocus
          />
          {unit && (
            <span className="px-3.5 py-1.5 mr-2 text-xs sm:text-sm font-semibold text-slate-500 bg-slate-200/80 rounded-lg">
              {unit}
            </span>
          )}
        </div>

        {errorMsg && (
          <p className="text-xs font-semibold text-red-600 text-left">
            ⚠️ {errorMsg}
          </p>
        )}
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        {question.allow_decline ? (
          <button
            type="button"
            id="btn-decline"
            onClick={onDecline}
            disabled={isSubmitting}
            className="w-full sm:w-auto px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors disabled:opacity-50"
          >
            {lang === "hi" ? "बताने में असुविधा है" : "Prefer not to say"}
          </button>
        ) : (
          <div />
        )}

        <button
          type="submit"
          id="btn-submit-number"
          disabled={!val.trim() || isSubmitting}
          className="w-full sm:w-auto px-8 py-3 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white font-bold text-sm sm:text-base rounded-xl shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isSubmitting ? (
            <span>{lang === "hi" ? "जाँच जारी है…" : "Evaluating…"}</span>
          ) : (
            <>
              <span>{lang === "hi" ? "भेजें" : "Submit"}</span>
              <span>→</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default NumberQuestion;
