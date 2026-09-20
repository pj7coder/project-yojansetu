"use client";

import React, { useState } from "react";
import { ConversationMessage, ExpectedInputDescriptor } from "../../types/citizen";

interface ConfirmationCardProps {
  message: ConversationMessage;
  expectedInput?: ExpectedInputDescriptor;
  lang?: "hi" | "en";
  isSubmitting?: boolean;
  onConfirmYes: () => void;
  onConfirmNo: () => void;
  onSendTextAnswer?: (text: string) => void;
}

export function ConfirmationCard({
  message,
  expectedInput,
  lang = "hi",
  isSubmitting = false,
  onConfirmYes,
  onConfirmNo,
  onSendTextAnswer,
}: ConfirmationCardProps) {
  const [customText, setCustomText] = useState("");
  const isHi = lang === "hi";

  const displayText = isHi ? message.text_hi : message.text_en;
  const secondaryText = isHi ? message.text_en : message.text_hi;

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customText.trim()) return;
    if (onSendTextAnswer) {
      onSendTextAnswer(customText.trim());
      setCustomText("");
    }
  };

  return (
    <div
      role="region"
      aria-labelledby="confirmation-title"
      className="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border-2 border-amber-200 space-y-6 transition-all"
    >
      {/* Badge Header */}
      <div className="space-y-1.5 text-left border-b border-amber-100 pb-4">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-300">
          <span>🔍</span>
          <span>{isHi ? "पुष्टि आवश्यक (Confirmation Required)" : "Confirmation Required"}</span>
        </div>

        <h2
          id="confirmation-title"
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

      {/* Confirmation Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={onConfirmYes}
          disabled={isSubmitting}
          className="w-full py-3.5 px-6 rounded-xl font-bold text-base text-white bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
        >
          <span className="text-xl">✅</span>
          <span>{isHi ? "हाँ, सही है" : "Yes, that's correct"}</span>
        </button>

        <button
          type="button"
          onClick={onConfirmNo}
          disabled={isSubmitting}
          className="w-full py-3.5 px-6 rounded-xl font-bold text-base text-slate-700 bg-slate-100 hover:bg-slate-200 active:scale-[0.98] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
        >
          <span className="text-xl">❌</span>
          <span>{isHi ? "नहीं, सुधारें" : "No, change it"}</span>
        </button>
      </div>

      {/* Optional: Type a correction or question */}
      {onSendTextAnswer && (
        <form onSubmit={handleCustomSubmit} className="pt-2 border-t border-slate-100 space-y-2">
          <label className="text-xs font-semibold text-slate-500 block">
            {isHi
              ? "या सुधार / सवाल यहाँ लिखें:"
              : "Or type a correction / question here:"}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder={isHi ? "उदा. 'मेरी उम्र 61 है' या 'यह क्यों चाहिए?'" : "e.g. 'My age is 61' or 'Why is this asked?'"}
              disabled={isSubmitting}
              className="flex-1 px-4 py-2.5 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            />
            <button
              type="submit"
              disabled={isSubmitting || !customText.trim()}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white text-sm font-semibold transition-all disabled:opacity-50"
            >
              {isHi ? "भेजें" : "Send"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default ConfirmationCard;
