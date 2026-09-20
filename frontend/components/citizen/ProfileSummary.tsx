"use client";

import React, { useState } from "react";

interface ProfileSummaryProps {
  profile: Record<string, any>;
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onUpdateFact?: (fieldName: string, value: any) => void;
  onEditFact?: (fieldName: string, value: any) => void;
  isUpdating?: boolean;
}

const FIELD_LABELS: Record<string, { hi: string; en: string }> = {
  age: { hi: "आयु", en: "Age" },
  state: { hi: "राज्य", en: "State" },
  district: { hi: "जिला", en: "District" },
  family_income: { hi: "पारिवारिक आय", en: "Family Income" },
  gender: { hi: "लिंग", en: "Gender" },
  rural_urban: { hi: "क्षेत्र", en: "Area" },
  occupation: { hi: "व्यवसाय", en: "Occupation" },
  farmer_category: { hi: "कृषक श्रेणी", en: "Farmer Category" },
  bpl_status: { hi: "बीपीएल स्थिति", en: "BPL Status" },
  disability_status: { hi: "दिव्यांगता", en: "Disability" },
  student_status: { hi: "विद्यार्थी", en: "Student" },
  marital_status: { hi: "वैवाहिक स्थिति", en: "Marital Status" },
  social_category: { hi: "सामाजिक श्रेणी", en: "Social Category" },
};

export function ProfileSummary({
  profile,
  lang: propLang,
  language,
  onUpdateFact,
  onEditFact,
  isUpdating = false,
}: ProfileSummaryProps) {
  const lang = language || propLang || "hi";
  const updateFact = onEditFact || onUpdateFact || (() => {});
  const [isOpen, setIsOpen] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const knownKeys = Object.keys(profile).filter(
    (k) => profile[k] !== undefined && profile[k] !== null
  );

  if (knownKeys.length === 0) {
    return null;
  }

  const formatValue = (key: string, val: any) => {
    if (typeof val === "boolean") {
      if (val) return lang === "hi" ? "हाँ" : "Yes";
      return lang === "hi" ? "नहीं" : "No";
    }
    if (key === "family_income") {
      try {
        const num = Number(val);
        return `₹${num.toLocaleString("en-IN")}`;
      } catch {
        return `₹${val}`;
      }
    }
    if (key === "age") {
      return lang === "hi" ? `${val} वर्ष` : `${val} years`;
    }
    return String(val);
  };

  const startEdit = (key: string, currentVal: any) => {
    setEditingField(key);
    setEditValue(String(currentVal));
  };

  const cancelEdit = () => {
    setEditingField(null);
    setEditValue("");
  };

  const saveEdit = (key: string) => {
    if (isUpdating) return;
    let finalVal: any = editValue.trim();

    if (key === "age" || key === "family_income") {
      const parsed = Number(finalVal);
      if (!isNaN(parsed)) {
        finalVal = parsed;
      }
    } else if (finalVal.toLowerCase() === "true" || finalVal === "हाँ") {
      finalVal = true;
    } else if (finalVal.toLowerCase() === "false" || finalVal === "नहीं") {
      finalVal = false;
    }

    updateFact(key, finalVal);
    setEditingField(null);
    setEditValue("");
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden text-left transition-all">
      {/* Accordion Toggle Header */}
      <button
        type="button"
        id="btn-toggle-profile-summary"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full px-4 py-3 bg-slate-50 hover:bg-slate-100 flex items-center justify-between transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500"
      >
        <div className="flex items-center gap-2">
          <span className="text-slate-600">👤</span>
          <span className="text-xs sm:text-sm font-bold text-slate-800">
            {lang === "hi" ? "आपकी जानकारी" : "Your Information"}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-semibold">
            {knownKeys.length}
          </span>
        </div>
        <span className="text-xs text-slate-500 font-semibold flex items-center gap-1">
          {isOpen ? (lang === "hi" ? "छिपाएँ ▲" : "Hide ▲") : (lang === "hi" ? "देखें / बदलें ▼" : "View / Edit ▼")}
        </span>
      </button>

      {/* Expanded Fact List */}
      {isOpen && (
        <div className="p-4 divide-y divide-slate-100 bg-white">
          <p className="text-xs text-slate-500 pb-2">
            {lang === "hi"
              ? "यदि कोई जानकारी गलत है तो आप सीधे यहाँ बदल सकते हैं:"
              : "If any fact needs correction, you can edit it directly:"}
          </p>

          {knownKeys.map((key) => {
            const labelObj = FIELD_LABELS[key] || {
              hi: key.replace(/_/g, " "),
              en: key.replace(/_/g, " "),
            };
            const label = lang === "hi" ? labelObj.hi : labelObj.en;
            const isBeingEdited = editingField === key;

            return (
              <div
                key={key}
                className="py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm"
              >
                <span className="font-semibold text-slate-700 min-w-[140px]">
                  {label}:
                </span>

                {isBeingEdited ? (
                  <div className="flex items-center gap-2 flex-1 max-w-xs">
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      disabled={isUpdating}
                      className="px-2 py-1 text-sm border border-orange-400 rounded-lg focus:outline-none focus:ring-1 focus:ring-orange-500 w-full"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => saveEdit(key)}
                      disabled={isUpdating}
                      className="px-2.5 py-1 text-xs font-bold text-white bg-orange-600 hover:bg-orange-700 rounded-md disabled:opacity-50"
                    >
                      {lang === "hi" ? "सहेजें" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEdit}
                      className="px-2 py-1 text-xs font-medium text-slate-600 hover:text-slate-900 rounded-md"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between sm:justify-end gap-3 flex-1">
                    <span className="font-bold text-slate-900">
                      {formatValue(key, profile[key])}
                    </span>
                    <button
                      type="button"
                      id={`btn-edit-${key}`}
                      onClick={() => startEdit(key, profile[key])}
                      className="text-xs text-orange-600 hover:text-orange-800 font-semibold px-2 py-0.5 rounded hover:bg-orange-50 transition-colors"
                    >
                      {lang === "hi" ? "बदलें" : "Edit"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ProfileSummary;
