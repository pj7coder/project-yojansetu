"use client";

import React from "react";
import { CitizenQuestionDisplay } from "../../types/citizen";
import { NumberQuestion } from "./NumberQuestion";
import { OptionQuestion } from "./OptionQuestion";
import { BooleanQuestion } from "./BooleanQuestion";
import { DistrictSelect } from "./DistrictSelect";

interface QuestionCardProps {
  question: CitizenQuestionDisplay;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onSubmitAnswer?: (fieldName: string, value: any) => void;
  onAnswer?: (fieldName: string, value: any) => void;
  onDeclineField?: (fieldName: string) => void;
  onDecline?: (fieldName: string) => void;
  onSkipField?: () => void;
  isSubmitting?: boolean;
  isLoading?: boolean;
}

export function QuestionCard({
  question,
  lang: propLang,
  language,
  onSubmitAnswer,
  onAnswer,
  onDeclineField,
  onDecline,
  onSkipField,
  isSubmitting: propIsSubmitting,
  isLoading,
}: QuestionCardProps) {
  const lang = language || propLang || "hi";
  const submitAnswer = onAnswer || onSubmitAnswer || (() => {});
  const declineField = onDecline || onDeclineField || (() => {});
  const isSubmitting = isLoading !== undefined ? isLoading : Boolean(propIsSubmitting);
  const primaryQuestion =
    lang === "hi" ? question.question_hi : question.question_en;
  const secondaryQuestion =
    lang === "hi" ? question.question_en : question.question_hi;

  const handleSubmit = (val: any) => {
    submitAnswer(question.field, val);
  };

  const handleDecline = () => {
    declineField(question.field);
  };

  return (
    <div
      role="region"
      aria-labelledby="question-title"
      className="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200 space-y-6 transition-all"
    >
      {/* Conversational Question Prompt */}
      <div className="space-y-1.5 text-left border-b border-slate-100 pb-4">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-50 text-orange-800 border border-orange-200">
          <span>🏛️</span>
          <span>
            {lang === "hi" ? "पात्रता प्रश्न" : "Eligibility Question"}
          </span>
        </div>

        <h2
          id="question-title"
          className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight leading-snug"
        >
          {primaryQuestion}
        </h2>

        {secondaryQuestion && (
          <p className="text-xs sm:text-sm text-slate-500 font-medium">
            {secondaryQuestion}
          </p>
        )}
      </div>

      {/* Dynamic Input Control Based on Field & Type */}
      <div className="pt-1">
        {question.field === "district" ? (
          <DistrictSelect
            question={question}
            lang={lang}
            onSubmit={handleSubmit}
            onDecline={handleDecline}
            isSubmitting={isSubmitting}
          />
        ) : question.data_type === "boolean" ? (
          <BooleanQuestion
            question={question}
            lang={lang}
            onSubmit={handleSubmit}
            onSkip={onSkipField || handleDecline}
            onDecline={handleDecline}
            isSubmitting={isSubmitting}
          />
        ) : question.data_type === "select" ? (
          <OptionQuestion
            question={question}
            lang={lang}
            onSubmit={handleSubmit}
            onDecline={handleDecline}
            isSubmitting={isSubmitting}
          />
        ) : question.data_type === "integer" ||
          question.data_type === "currency" ||
          question.data_type === "number" ? (
          <NumberQuestion
            question={question}
            lang={lang}
            onSubmit={handleSubmit}
            onDecline={handleDecline}
            isSubmitting={isSubmitting}
          />
        ) : (
          <div className="text-center text-sm text-slate-500">
            {/* Safe text fallback */}
            <OptionQuestion
              question={question}
              lang={lang}
              onSubmit={handleSubmit}
              onDecline={handleDecline}
              isSubmitting={isSubmitting}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default QuestionCard;
