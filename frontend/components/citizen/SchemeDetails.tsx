"use client";

import React from "react";
import { CitizenSchemeDetail } from "../../types/citizen";

interface SchemeDetailsProps {
  scheme: CitizenSchemeDetail;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onBack?: () => void;
}

export function SchemeDetails({ scheme, lang: propLang, language, onBack }: SchemeDetailsProps) {
  const lang = language || propLang || "hi";
  const displayName =
    lang === "hi"
      ? scheme.name_hi || scheme.name_en
      : scheme.name_en;

  const subtitleName =
    lang === "hi" && scheme.name_hi && scheme.name_hi !== scheme.name_en
      ? scheme.name_en
      : null;

  const department =
    lang === "hi"
      ? scheme.department_hi || scheme.department_en
      : scheme.department_en;

  const category =
    lang === "hi"
      ? scheme.category_hi || scheme.category_en
      : scheme.category_en;

  const purpose =
    lang === "hi"
      ? scheme.purpose_hi || scheme.purpose_en
      : scheme.purpose_en;

  const whyEligibleList =
    lang === "hi" ? scheme.why_eligible_hi : scheme.why_eligible_en;

  return (
    <div
      role="region"
      aria-label="Scheme Details"
      className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 text-left space-y-8 animate-fadeIn"
    >
      {/* Top Bar: Back Action & Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        {onBack && (
          <button
            type="button"
            id="btn-back-to-results"
            onClick={onBack}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs sm:text-sm font-bold text-slate-700 hover:text-orange-700 bg-slate-100 hover:bg-orange-50 rounded-lg transition-colors cursor-pointer"
          >
            <span>←</span>
            <span>{lang === "hi" ? "परिणामों पर लौटें" : "Back to Results"}</span>
          </button>
        )}

        <div className="flex items-center gap-2">
          {department && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
              {department}
            </span>
          )}
          {category && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-50 text-orange-800 border border-orange-200">
              {category}
            </span>
          )}
        </div>
      </div>

      {/* Main Title & Status */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-snug">
            {displayName}
          </h1>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
            {lang === "hi" ? "सत्यापित योजना" : "Verified Scheme"}
          </span>
        </div>
        {subtitleName && (
          <p className="text-sm sm:text-base text-slate-500 font-medium">
            {subtitleName}
          </p>
        )}
      </div>

      {/* Overview & Purpose */}
      {purpose && (
        <section className="space-y-2 bg-slate-50/80 rounded-xl p-4 border border-slate-200/70">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            {lang === "hi" ? "योजना का उद्देश्य" : "Scheme Objective"}
          </h2>
          <p className="text-sm sm:text-base text-slate-800 leading-relaxed">
            {purpose}
          </p>
        </section>
      )}

      {/* Why You Are Eligible (Matched Criteria from Day 14) */}
      {whyEligibleList && whyEligibleList.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base sm:text-lg font-bold text-emerald-950 flex items-center gap-2">
            <span>✅</span>
            <span>
              {lang === "hi" ? "आप क्यों पात्र हैं" : "Why You Are Eligible"}
            </span>
          </h2>
          <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-xl p-4 space-y-2">
            {whyEligibleList.map((reason, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm text-emerald-900">
                <span className="text-emerald-600 font-bold shrink-0 mt-0.5">✓</span>
                <span className="font-medium">{reason}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Scheme Benefits */}
      {scheme.benefits && scheme.benefits.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
            <span>🎁</span>
            <span>{lang === "hi" ? "योजना के लाभ" : "Scheme Benefits"}</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {scheme.benefits.map((b, idx) => (
              <div
                key={idx}
                className="bg-orange-50/60 border border-orange-200 rounded-xl p-4 space-y-1 text-left"
              >
                {b.display_text_hi || b.display_text_en ? (
                  <div className="text-base font-extrabold text-orange-950">
                    {lang === "hi"
                      ? b.display_text_hi || b.display_text_en
                      : b.display_text_en || b.display_text_hi}
                  </div>
                ) : null}
                <div className="text-xs text-orange-800 font-medium">
                  {lang === "hi"
                    ? b.description_hi || b.description_en
                    : b.description_en || b.description_hi}
                </div>
                <div className="text-[11px] text-slate-500 font-semibold uppercase">
                  {b.benefit_type} {b.frequency ? `• ${b.frequency}` : ""}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Required Documents Checklist */}
      {scheme.required_documents && scheme.required_documents.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
            <span>📄</span>
            <span>
              {lang === "hi" ? "आवश्यक दस्तावेज" : "Required Documents"}
            </span>
          </h2>
          <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden bg-slate-50/30">
            {scheme.required_documents.map((d, idx) => (
              <div
                key={idx}
                className="p-3 sm:p-4 flex items-center justify-between gap-3 text-sm"
              >
                <div className="space-y-0.5">
                  <div className="font-bold text-slate-900">
                    {lang === "hi"
                      ? d.document_name_hi || d.document_name_en
                      : d.document_name_en}
                  </div>
                  {d.description_en && (
                    <div className="text-xs text-slate-500">
                      {lang === "hi"
                        ? d.description_hi || d.description_en
                        : d.description_en}
                    </div>
                  )}
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${
                    d.is_mandatory
                      ? "bg-red-50 text-red-700 border border-red-200"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {d.is_mandatory
                    ? lang === "hi"
                      ? "अनिवार्य"
                      : "Mandatory"
                    : lang === "hi"
                    ? "यदि उपलब्ध हो"
                    : "Optional"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* How to Apply */}
      {scheme.application && (
        <section className="space-y-4">
          <h2 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2">
            <span>📝</span>
            <span>
              {lang === "hi" ? "आवेदन की प्रक्रिया" : "How to Apply"}
            </span>
          </h2>

          {/* Delivery Channels */}
          {scheme.application.channels?.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                {lang === "hi" ? "उपलब्ध माध्यम" : "Available Channels"}
              </span>
              <div className="flex flex-wrap gap-2">
                {scheme.application.channels.map((ch, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1 bg-slate-100 text-slate-800 rounded-lg text-xs font-semibold border border-slate-200"
                  >
                    🏢 {ch}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Ordered Steps */}
          {scheme.application.steps_en?.length > 0 && (
            <ol className="space-y-2.5 bg-slate-50 rounded-xl p-4 border border-slate-200/80 list-decimal list-inside text-sm text-slate-800">
              {(lang === "hi"
                ? scheme.application.steps_hi
                : scheme.application.steps_en
              ).map((step, idx) => (
                <li key={idx} className="leading-relaxed font-medium">
                  {step}
                </li>
              ))}
            </ol>
          )}

          {/* Official Portal Button */}
          {scheme.application.is_portal_url_safe &&
            scheme.application.portal_url && (
              <div className="pt-2">
                <a
                  href={scheme.application.portal_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-bold text-sm rounded-xl shadow-sm transition-all active:scale-95"
                >
                  <span>
                    {lang === "hi"
                      ? "आवेदन वेबसाइट खोलें"
                      : "Open Application Portal"}
                  </span>
                  <span>↗</span>
                </a>
              </div>
            )}

          {/* Disclaimer Note */}
          <p className="text-xs text-slate-500 italic bg-slate-100/70 p-3 rounded-lg border border-slate-200/60">
            ℹ️{" "}
            {lang === "hi"
              ? scheme.application.guidance_note_hi
              : scheme.application.guidance_note_en}
          </p>
        </section>
      )}

      {/* Official Government Source */}
      {scheme.official_source && (
        <section className="space-y-2 pt-4 border-t border-slate-200 text-xs text-slate-500">
          <h2 className="font-bold uppercase tracking-wider text-slate-600">
            {lang === "hi" ? "आधिकारिक स्रोत" : "Official Source Reference"}
          </h2>
          <div className="space-y-1">
            {scheme.official_source.department_en && (
              <p>
                <span className="font-semibold">
                  {lang === "hi" ? "विभाग:" : "Department:"}
                </span>{" "}
                {lang === "hi"
                  ? scheme.official_source.department_hi ||
                    scheme.official_source.department_en
                  : scheme.official_source.department_en}
              </p>
            )}
            {scheme.official_source.notification_reference && (
              <p>
                <span className="font-semibold">
                  {lang === "hi" ? "अधिसूचना / परिपत्र:" : "Notification/Order:"}
                </span>{" "}
                {scheme.official_source.notification_reference}
              </p>
            )}
            <p>
              <span className="font-semibold">
                {lang === "hi" ? "सत्यापित संस्करण:" : "Verified Version:"}
              </span>{" "}
              v{scheme.version_number}{" "}
              {scheme.effective_date
                ? `(प्रभावी: ${scheme.effective_date})`
                : ""}
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

export default SchemeDetails;
