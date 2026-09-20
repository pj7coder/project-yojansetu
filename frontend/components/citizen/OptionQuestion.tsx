"use client";

import React, { useState } from "react";
import { CitizenQuestionDisplay, QuestionOption } from "../../types/citizen";

interface OptionQuestionProps {
  question: CitizenQuestionDisplay;
  lang: "hi" | "en";
  onSubmit: (value: string) => void;
  onDecline: () => void;
  isSubmitting: boolean;
}

export function OptionQuestion({
  question,
  lang,
  onSubmit,
  onDecline,
  isSubmitting,
}: OptionQuestionProps) {
  const [selectedVal, setSelectedVal] = useState<string | null>(null);

  const options: QuestionOption[] = question.options || [];

  const handleSelect = (val: string) => {
    if (isSubmitting) return;
    setSelectedVal(val);
    onSubmit(val);
  };

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

      {/* Grid of Option Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {options.map((opt) => {
          const isSelected = selectedVal === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              id={`option-${opt.value.toLowerCase()}`}
              onClick={() => handleSelect(opt.value)}
              disabled={isSubmitting}
              className={`min-h-[50px] p-3 rounded-xl border text-left flex items-center justify-between transition-all duration-150 active:scale-[0.98] disabled:opacity-50 ${
                isSelected
                  ? "bg-orange-50 border-orange-500 text-orange-950 ring-2 ring-orange-500/20 shadow-xs"
                  : "bg-white hover:bg-slate-50 border-slate-200 text-slate-800 shadow-2xs hover:border-slate-300"
              }`}
            >
              <div className="space-y-0.5">
                <div className="text-sm font-bold leading-snug">
                  {lang === "hi" ? opt.label_hi : opt.label_en}
                </div>
                <div className="text-xs text-slate-500 font-medium">
                  {lang === "hi" ? opt.label_en : opt.label_hi}
                </div>
              </div>
              <div
                className={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors shrink-0 ml-2 ${
                  isSelected
                    ? "border-orange-600 bg-orange-600 text-white"
                    : "border-slate-300 bg-white"
                }`}
              >
                {isSelected && (
                  <svg
                    className="w-3 h-3 fill-current"
                    viewBox="0 0 20 20"
                  >
                    <path d="M0 11l2-2 5 5L18 3l2 2L7 18z" />
                  </svg>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Decline action */}
      {question.allow_decline && (
        <div className="pt-2 text-center sm:text-left">
          <button
            type="button"
            id="btn-decline-option"
            onClick={onDecline}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors disabled:opacity-50"
          >
            {lang === "hi" ? "बताने में असुविधा है" : "Prefer not to say"}
          </button>
        </div>
      )}
    </div>
  );
}

export default OptionQuestion;
