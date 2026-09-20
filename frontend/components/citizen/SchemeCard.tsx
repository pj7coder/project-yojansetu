"use client";

import React from "react";
import { CitizenSchemeCard } from "../../types/citizen";

interface SchemeCardProps {
  scheme: CitizenSchemeCard;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onSelectScheme?: (schemeId: string) => void;
  onSelect?: () => void;
}

export function SchemeCard({
  scheme,
  lang,
  language,
  onSelectScheme,
  onSelect,
}: SchemeCardProps) {
  const activeLang = language || lang || "hi";
  const handleSelect = () => {
    if (onSelect) onSelect();
    else if (onSelectScheme) onSelectScheme(scheme.scheme_id);
  };
  const isEligible = scheme.eligibility_status === "ELIGIBLE";

  const displayName =
    activeLang === "hi"
      ? scheme.name_hi || scheme.name_en
      : scheme.name_en;

  const subtitleName =
    activeLang === "hi" && scheme.name_hi && scheme.name_hi !== scheme.name_en
      ? scheme.name_en
      : null;

  const department =
    activeLang === "hi"
      ? scheme.department_hi || scheme.department_en
      : scheme.department_en;

  const purpose =
    lang === "hi"
      ? scheme.purpose_hi || scheme.purpose_en
      : scheme.purpose_en;

  const primaryBenefit =
    lang === "hi"
      ? scheme.primary_benefit_hi || scheme.primary_benefit_en
      : scheme.primary_benefit_en;

  return (
    <div
      role="article"
      className={`bg-white rounded-2xl p-5 sm:p-6 border transition-all duration-200 flex flex-col justify-between text-left space-y-4 shadow-xs hover:shadow-md ${
        isEligible
          ? "border-emerald-200 hover:border-emerald-300"
          : "border-amber-200 hover:border-amber-300"
      }`}
    >
      <div className="space-y-3">
        {/* Header Badges: Department & Status */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          {department && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
              {department}
            </span>
          )}

          <span
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold ${
              isEligible
                ? "bg-emerald-100 text-emerald-800"
                : "bg-amber-100 text-amber-800"
            }`}
          >
            <span>{isEligible ? "✓" : "ℹ"}</span>
            <span>
              {isEligible
                ? lang === "hi"
                  ? "पात्र"
                  : "Eligible"
                : lang === "hi"
                ? "और जानकारी चाहिए"
                : "More Info Needed"}
            </span>
          </span>
        </div>

        {/* Title */}
        <div className="space-y-0.5">
          <h3 className="text-lg sm:text-xl font-bold text-slate-900 leading-tight">
            {displayName}
          </h3>
          {subtitleName && (
            <p className="text-xs text-slate-500 font-medium">
              {subtitleName}
            </p>
          )}
        </div>

        {/* Purpose / Description */}
        {purpose && (
          <p className="text-xs sm:text-sm text-slate-600 line-clamp-2 leading-relaxed">
            {purpose}
          </p>
        )}

        {/* Benefit Highlight Box */}
        {primaryBenefit && (
          <div className="bg-orange-50/80 border border-orange-200/70 rounded-xl px-3.5 py-2 flex items-center gap-2">
            <span className="text-base sm:text-lg">💰</span>
            <div>
              <div className="text-xs font-semibold text-orange-800 uppercase tracking-wider">
                {lang === "hi" ? "मुख्य लाभ" : "Primary Benefit"}
              </div>
              <div className="text-sm font-extrabold text-orange-950">
                {primaryBenefit}
              </div>
            </div>
          </div>
        )}

        {/* Why Eligible Highlights */}
        {isEligible && scheme.why_eligible_summary_hi?.length > 0 && (
          <div className="space-y-1 text-xs text-emerald-800">
            {(lang === "hi"
              ? scheme.why_eligible_summary_hi
              : scheme.why_eligible_summary_en
            )
              .slice(0, 2)
              .map((reason, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{reason}</span>
                </div>
              ))}
          </div>
        )}

        {/* Missing fields if more info required */}
        {!isEligible && scheme.missing_fields_display_hi?.length > 0 && (
          <div className="space-y-1 text-xs text-amber-800">
            <p className="font-semibold">
              {lang === "hi" ? "पुष्टि हेतु आवश्यक:" : "Needed to confirm:"}
            </p>
            {(lang === "hi"
              ? scheme.missing_fields_display_hi
              : scheme.missing_fields_display_en
            )
              .slice(0, 2)
              .map((field, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <span className="text-amber-600">•</span>
                  <span>{field}</span>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Action Button */}
      <button
        type="button"
        id={`btn-view-scheme-${scheme.scheme_id}`}
        onClick={handleSelect}
        className="w-full mt-2 py-2.5 px-4 rounded-xl font-bold text-xs sm:text-sm bg-slate-100 hover:bg-orange-600 hover:text-white text-slate-800 transition-colors flex items-center justify-center gap-1.5 shadow-2xs group cursor-pointer"
      >
        <span>
          {activeLang === "hi" ? "योजना का विवरण देखें" : "View Scheme Details"}
        </span>
        <span className="group-hover:translate-x-0.5 transition-transform">
          →
        </span>
      </button>
    </div>
  );
}

export default SchemeCard;
