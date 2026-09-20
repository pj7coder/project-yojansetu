"use client";

import React, { useState } from "react";
import { ConversationMessage, ExpectedInputDescriptor } from "../../types/citizen";

interface ClarificationCardProps {
  message: ConversationMessage;
  expectedInput?: ExpectedInputDescriptor;
  lang?: "hi" | "en";
  isSubmitting?: boolean;
  onSubmitText: (text: string) => void;
  onSkipField?: () => void;
}

export function ClarificationCard({
  message,
  expectedInput,
  lang = "hi",
  isSubmitting = false,
  onSubmitText,
  onSkipField,
}: ClarificationCardProps) {
  const [inputText, setInputText] = useState("");
  const isHi = lang === "hi";

  const displayText = isHi ? message.text_hi : message.text_en;
  const secondaryText = isHi ? message.text_en : message.text_hi;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSubmitText(inputText.trim());
    setInputText("");
  };

  return (
    <div
      role="region"
      aria-labelledby="clarification-title"
      className="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border-2 border-indigo-200 space-y-6 transition-all"
    >
      {/* Badge Header */}
      <div className="space-y-1.5 text-left border-b border-indigo-100 pb-4">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-900 border border-indigo-200">
          <span>ℹ️</span>
          <span>{isHi ? "स्पष्टीकरण आवश्यक (Clarification Needed)" : "Clarification Needed"}</span>
        </div>

        <h2
          id="clarification-title"
          className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight leading-snug"
        >
          {displayText}
        </h2>

        {secondaryText && (
          <p className="text-xs sm:text-sm text-slate-500 font-medium">
            {secondaryText}
          </p>
        )}
      </div>

      {/* Suggested Quick Options if available */}
      {expectedInput?.options && expectedInput.options.length > 0 && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-500 block">
            {isHi ? "सुझाए गए विकल्प चुनें:" : "Select suggested option:"}
          </label>
          <div className="grid grid-cols-2 gap-2">
            {expectedInput.options.map((opt, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onSubmitText(String(opt.value))}
                disabled={isSubmitting}
                className="py-2.5 px-4 rounded-xl border border-slate-200 hover:border-indigo-500 hover:bg-indigo-50 text-sm font-medium text-slate-800 transition-all text-left"
              >
                {isHi ? opt.label_hi : opt.label_en}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Direct Input Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              isHi
                ? expectedInput?.placeholder_hi || "कृपया स्पष्ट उत्तर यहाँ लिखें..."
                : expectedInput?.placeholder_en || "Please enter clear answer..."
            }
            disabled={isSubmitting}
            className="flex-1 px-4 py-3 rounded-xl border border-slate-300 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            autoFocus
          />
          <button
            type="submit"
            disabled={isSubmitting || !inputText.trim()}
            className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm transition-all shadow-sm disabled:opacity-50"
          >
            {isHi ? "आगे बढ़ें" : "Submit"}
          </button>
        </div>

        {onSkipField && (
          <div className="text-right">
            <button
              type="button"
              onClick={onSkipField}
              disabled={isSubmitting}
              className="text-xs text-slate-500 hover:text-slate-800 underline font-medium cursor-pointer"
            >
              {isHi ? "इस प्रश्न को छोड़ें (पता नहीं)" : "Skip this question (Don't know)"}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}

export default ClarificationCard;
