"use client";

import React, { useState, useEffect, useRef } from "react";
import { RajasthanDistrictItem } from "../../types/citizen";
import { getRajasthanDistricts } from "../../lib/api";

export interface CitizenParameters {
  age: number | null;
  gender: "MALE" | "FEMALE" | "OTHER" | null;
  category: "GENERAL" | "OBC" | "SC" | "ST" | "EWS" | "MBC" | null;
  income: number | null;
  occupation: string | null;
  residence: "RURAL" | "URBAN" | null;
  state: string | null;
  district: string | null;
  rationCard: "NONE" | "BPL" | "STATE_BPL" | "AAY" | "NFSA" | null;
  isWidow: boolean;
  isDisabled: boolean;
  disabilityPercent: number;
  landBigha: number | null;
  hasJanAadhaar: boolean | null;
  isStudent: boolean;
  maritalStatus: "MARRIED" | "SINGLE" | "WIDOW" | "DIVORCED" | null;
}

export const DEFAULT_CITIZEN_PARAMETERS: CitizenParameters = {
  age: null,
  gender: null,
  category: null,
  income: null,
  occupation: null,
  residence: null,
  state: null,
  district: null,
  rationCard: null,
  isWidow: false,
  isDisabled: false,
  disabilityPercent: 40,
  landBigha: null,
  hasJanAadhaar: null,
  isStudent: false,
  maritalStatus: null,
};

interface CitizenParameterPanelProps {
  parameters: CitizenParameters;
  onChange: (newParams: CitizenParameters) => void;
  onApplyToChat: (params: CitizenParameters) => void;
  lang: "hi" | "en";
  isOpen?: boolean;
  onClose?: () => void;
  lastUpdatedField?: string | null;
}

export function CitizenParameterPanel({
  parameters,
  onChange,
  onApplyToChat,
  lang = "hi",
  isOpen = true,
  onClose,
  lastUpdatedField,
}: CitizenParameterPanelProps) {
  const isHi = lang === "hi";
  const [districts, setDistricts] = useState<RajasthanDistrictItem[]>([]);

  // Smooth slider display values (visibly animated when changed)
  const [displayedAge, setDisplayedAge] = useState<number>(parameters.age ?? 0);
  const [displayedIncome, setDisplayedIncome] = useState<number>(parameters.income ?? 0);
  const [highlightedField, setHighlightedField] = useState<string | null>(null);

  const prevAgeRef = useRef<number | null>(parameters.age);
  const prevIncomeRef = useRef<number | null>(parameters.income);
  const ageAnimRef = useRef<number | null>(null);
  const incomeAnimRef = useRef<number | null>(null);

  useEffect(() => {
    getRajasthanDistricts()
      .then((data) => setDistricts(data))
      .catch(() => {});
  }, []);

  // Smooth animation helper
  const animateValue = (
    from: number,
    to: number,
    durationMs: number,
    onStep: (val: number) => void,
    animRef: React.MutableRefObject<number | null>
  ) => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    const startTime = performance.now();
    const step = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // Easing out cubic for natural deceleration
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(from + (to - from) * ease);
      onStep(current);
      if (progress < 1) {
        animRef.current = requestAnimationFrame(step);
      } else {
        animRef.current = null;
      }
    };
    animRef.current = requestAnimationFrame(step);
  };

  // Visibly animate age slider moving when parameters.age changes
  useEffect(() => {
    if (parameters.age !== null && parameters.age !== prevAgeRef.current) {
      const from = prevAgeRef.current ?? 18;
      const to = parameters.age;
      prevAgeRef.current = to;
      animateValue(from, to, 600, (val) => setDisplayedAge(val), ageAnimRef);
      setHighlightedField("age");
      const timer = setTimeout(() => setHighlightedField(null), 3000);
      return () => clearTimeout(timer);
    } else if (parameters.age === null) {
      prevAgeRef.current = null;
      setDisplayedAge(0);
    }
  }, [parameters.age]);

  // Visibly animate income slider moving when parameters.income changes
  useEffect(() => {
    if (parameters.income !== null && parameters.income !== prevIncomeRef.current) {
      const from = prevIncomeRef.current ?? 0;
      const to = parameters.income;
      prevIncomeRef.current = to;
      animateValue(from, to, 600, (val) => setDisplayedIncome(val), incomeAnimRef);
      setHighlightedField("income");
      const timer = setTimeout(() => setHighlightedField(null), 3000);
      return () => clearTimeout(timer);
    } else if (parameters.income === null) {
      prevIncomeRef.current = null;
      setDisplayedIncome(0);
    }
  }, [parameters.income]);

  // Track external highlight prop
  useEffect(() => {
    if (lastUpdatedField) {
      setHighlightedField(lastUpdatedField);
      const timer = setTimeout(() => setHighlightedField(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [lastUpdatedField]);

  const update = <K extends keyof CitizenParameters>(key: K, val: CitizenParameters[K]) => {
    onChange({
      ...parameters,
      [key]: val,
    });
  };

  const updateMany = (updates: Partial<CitizenParameters>) => {
    onChange({
      ...parameters,
      ...updates,
    });
  };

  // 1-Click Preset Personas
  const applyPreset = (preset: "FARMER" | "SENIOR" | "STUDENT" | "WIDOW") => {
    if (preset === "FARMER") {
      onChange({
        ...parameters,
        age: 48,
        gender: "MALE",
        category: "OBC",
        income: 90000,
        occupation: "FARMER",
        residence: "RURAL",
        district: "Sikar",
        rationCard: "BPL",
        landBigha: 3,
        isDisabled: false,
        isWidow: false,
        isStudent: false,
        maritalStatus: "MARRIED",
      });
    } else if (preset === "SENIOR") {
      onChange({
        ...parameters,
        age: 65,
        gender: "MALE",
        category: "SC",
        income: 48000,
        occupation: "RETIRED",
        residence: "RURAL",
        district: "Jaipur",
        rationCard: "AAY",
        landBigha: 0,
        isDisabled: false,
        isWidow: false,
        isStudent: false,
        maritalStatus: "MARRIED",
      });
    } else if (preset === "STUDENT") {
      onChange({
        ...parameters,
        age: 20,
        gender: "FEMALE",
        category: "ST",
        income: 60000,
        occupation: "STUDENT",
        residence: "RURAL",
        district: "Udaipur",
        rationCard: "BPL",
        landBigha: 1,
        isDisabled: false,
        isWidow: false,
        isStudent: true,
        maritalStatus: "SINGLE",
      });
    } else if (preset === "WIDOW") {
      onChange({
        ...parameters,
        age: 52,
        gender: "FEMALE",
        category: "OBC",
        income: 36000,
        occupation: "HOMEMAKER",
        residence: "RURAL",
        district: "Jodhpur",
        rationCard: "BPL",
        isWidow: true,
        isDisabled: false,
        isStudent: false,
        maritalStatus: "WIDOW",
        landBigha: 0,
      });
    }
  };

  // Helper for dynamic highlight classes
  const getHighlightClass = (fieldName: string) => {
    return highlightedField === fieldName
      ? "ring-2 ring-orange-500 bg-orange-50/70 shadow-sm rounded-xl p-2 transition-all duration-500 animate-pulse"
      : "transition-all duration-300";
  };

  return (
    <aside
      className={`h-full flex flex-col bg-white border-l border-slate-200 transition-all duration-200 z-20 shadow-lg lg:shadow-none ${
        isOpen ? "w-80 sm:w-96 flex-shrink-0" : "hidden"
      }`}
    >
      {/* Header */}
      <div className="p-3.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">⚙️</span>
          <div>
            <h2 className="text-xs font-black uppercase tracking-wider text-slate-800">
              {isHi ? "नागरिक पैरामीटर" : "Citizen Parameters"}
            </h2>
            <p className="text-[10px] text-slate-500">
              {isHi ? "बोलकर या चुनकर विवरण बदलें" : "Speaks or tap to change details"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onChange(DEFAULT_CITIZEN_PARAMETERS)}
            title={isHi ? "सभी विवरण रीसेट करें" : "Clear all details"}
            className="px-2 py-1 text-[11px] font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-md hover:bg-slate-100 transition cursor-pointer"
          >
            {isHi ? "रीसेट (खाली करें)" : "Reset"}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="lg:hidden p-1 rounded hover:bg-slate-200 text-slate-500 text-sm cursor-pointer"
            >
              ✕
            </button>
          )}
        </div>
      </div>


      {/* Main Parameters Form */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4 text-xs scrollbar-thin">
        {/* 1. Age (With Visible Moving Slider Animation) */}
        <div className={`space-y-1.5 ${getHighlightClass("age")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>🎂</span>
              <span>{isHi ? "आयु (वर्ष)" : "Age (Years)"}</span>
              {highlightedField === "age" && (
                <span className="text-[9px] text-orange-600 bg-orange-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "स्वतः अपडेट" : "Auto-Updated"}
                </span>
              )}
            </label>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => update("age", Math.max(10, (parameters.age ?? 18) - 1))}
                className="w-5 h-5 rounded bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 hover:bg-slate-200 cursor-pointer"
              >
                -
              </button>
              <span className="font-black text-slate-900 min-w-10 text-center bg-slate-50 py-0.5 rounded border border-slate-200 text-xs">
                {parameters.age !== null ? `${displayedAge || parameters.age} वर्ष` : "--"}
              </span>
              <button
                type="button"
                onClick={() => update("age", Math.min(100, (parameters.age ?? 18) + 1))}
                className="w-5 h-5 rounded bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 hover:bg-slate-200 cursor-pointer"
              >
                +
              </button>
            </div>
          </div>

          {/* Range Slider - Visibly animates moving thumb */}
          <div className="relative pt-1">
            <input
              type="range"
              min="10"
              max="95"
              value={parameters.age !== null ? displayedAge : 10}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                setDisplayedAge(val);
                update("age", val);
              }}
              className={`w-full accent-orange-600 cursor-pointer h-2 bg-slate-200 rounded-lg transition-all ${
                parameters.age === null ? "opacity-50" : "opacity-100"
              }`}
            />
            {parameters.age === null && (
              <span className="text-[10px] text-slate-400 italic block text-right mt-0.5">
                {isHi ? "कोई आयु निर्धारित नहीं" : "No age set (Move slider or speak)"}
              </span>
            )}
          </div>
        </div>

        {/* 2. Gender */}
        <div className={`space-y-1.5 ${getHighlightClass("gender")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>⚧️</span>
              <span>{isHi ? "लिंग" : "Gender"}</span>
              {highlightedField === "gender" && (
                <span className="text-[9px] text-orange-600 bg-orange-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "पहचाना गया" : "Detected"}
                </span>
              )}
            </label>
            {parameters.gender !== null && (
              <button
                type="button"
                onClick={() => update("gender", null)}
                className="text-[10px] text-slate-400 hover:text-slate-600 underline"
              >
                {isHi ? "हटाएं" : "Clear"}
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
            {[
              { id: "MALE", hi: "पुरुष", en: "Male" },
              { id: "FEMALE", hi: "महिला", en: "Female" },
              { id: "OTHER", hi: "अन्य", en: "Other" },
            ].map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => {
                  if (g.id !== "FEMALE") {
                    updateMany({
                      gender: g.id as any,
                      isWidow: false,
                      maritalStatus: parameters.maritalStatus === "WIDOW" ? null : parameters.maritalStatus,
                    });
                  } else {
                    update("gender", "FEMALE");
                  }
                }}
                className={`py-1.5 px-2 rounded-md font-bold text-[11px] transition cursor-pointer ${
                  parameters.gender === g.id
                    ? "bg-white text-orange-600 shadow-xs ring-1 ring-orange-500/30"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {isHi ? g.hi : g.en}
              </button>
            ))}
          </div>
        </div>

        {/* 3. Social Category */}
        <div className={`space-y-1.5 ${getHighlightClass("category")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>🏷️</span>
              <span>{isHi ? "जाति श्रेणी" : "Social Category"}</span>
              {highlightedField === "category" && (
                <span className="text-[9px] text-orange-600 bg-orange-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "अपडेट" : "Updated"}
                </span>
              )}
            </label>
            {parameters.category !== null && (
              <button
                type="button"
                onClick={() => update("category", null)}
                className="text-[10px] text-slate-400 hover:text-slate-600 underline"
              >
                {isHi ? "हटाएं" : "Clear"}
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-1">
            {(["GENERAL", "OBC", "SC", "ST", "EWS", "MBC"] as const).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => update("category", cat)}
                className={`py-1 rounded-lg border text-[11px] font-bold transition cursor-pointer ${
                  parameters.category === cat
                    ? "bg-orange-600 text-white border-orange-600 shadow-xs ring-1 ring-orange-600"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* 4. Annual Income (With Slider Animation) */}
        <div className={`space-y-1.5 ${getHighlightClass("income")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>💰</span>
              <span>{isHi ? "वार्षिक पारिवारिक आय" : "Annual Income"}</span>
              {highlightedField === "income" && (
                <span className="text-[9px] text-emerald-700 bg-emerald-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "स्वतः अपडेट" : "Auto-Updated"}
                </span>
              )}
            </label>
            <span className="font-black text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[11px]">
              {parameters.income !== null
                ? `₹${(displayedIncome || parameters.income).toLocaleString("en-IN")}`
                : "--"}
            </span>
          </div>

          <div className="grid grid-cols-4 gap-1">
            {[
              { label: "₹0", val: 0 },
              { label: "50K", val: 50000 },
              { label: "1.2L", val: 120000 },
              { label: "2.5L+", val: 250000 },
            ].map((p) => (
              <button
                key={p.val}
                type="button"
                onClick={() => update("income", p.val)}
                className={`py-1 rounded border text-[10px] font-bold transition cursor-pointer ${
                  parameters.income === p.val
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-2xs"
                    : "bg-slate-50 text-slate-600 border-slate-200 hover:border-slate-300"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <input
            type="range"
            min="0"
            max="600000"
            step="10000"
            value={parameters.income !== null ? displayedIncome : 0}
            onChange={(e) => {
              const val = parseInt(e.target.value) || 0;
              setDisplayedIncome(val);
              update("income", val);
            }}
            className={`w-full accent-emerald-600 cursor-pointer h-1.5 bg-slate-200 rounded-lg mt-1 transition-all ${
              parameters.income === null ? "opacity-50" : "opacity-100"
            }`}
          />
        </div>

        {/* 5. Occupation */}
        <div className={`space-y-1.5 ${getHighlightClass("occupation")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>💼</span>
              <span>{isHi ? "व्यवसाय / कार्य" : "Occupation"}</span>
              {highlightedField === "occupation" && (
                <span className="text-[9px] text-orange-600 bg-orange-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "पहचाना गया" : "Detected"}
                </span>
              )}
            </label>
          </div>
          <select
            value={parameters.occupation ?? ""}
            onChange={(e) => {
              const occ = e.target.value || null;
              updateMany({
                occupation: occ,
                isStudent: occ === "STUDENT",
              });
            }}
            className="w-full p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-medium text-slate-800 focus:outline-none focus:border-orange-500 cursor-pointer"
          >
            <option value="">{isHi ? "-- कोई व्यवसाय नहीं चुना (None) --" : "-- None Selected --"}</option>
            <option value="FARMER">{isHi ? "कृषक / किसान (Farmer)" : "Farmer"}</option>
            <option value="LABORER">{isHi ? "दिहाड़ी श्रमिक / मजदूर (Daily Wage)" : "Laborer / Daily Wage"}</option>
            <option value="STUDENT">{isHi ? "विद्यार्थी / छात्र (Student)" : "Student"}</option>
            <option value="SELF_EMPLOYED">{isHi ? "स्वरोजगार / छोटा व्यापारी (Self Employed)" : "Self Employed"}</option>
            <option value="HOMEMAKER">{isHi ? "गृहणी (Homemaker)" : "Homemaker"}</option>
            <option value="UNEMPLOYED">{isHi ? "बेरोजगार युवा (Unemployed)" : "Unemployed"}</option>
            <option value="RETIRED">{isHi ? "वरिष्ठ / सेवानिवृत्त (Retired)" : "Retired"}</option>
          </select>
        </div>

        {/* 6. Location: State & District */}
        <div className="space-y-2">
          <div className={`space-y-1 ${getHighlightClass("state")}`}>
            <label className="font-bold text-slate-700 text-[11px] flex items-center justify-between">
              <span>🇮🇳 {isHi ? "राज्य / केंद्र शासित प्रदेश" : "State / UT (All India)"}</span>
              {parameters.state && (
                <button
                  type="button"
                  onClick={() => update("state", null)}
                  className="text-[10px] text-slate-400 hover:text-slate-600 underline"
                >
                  {isHi ? "रीसेट" : "Reset"}
                </button>
              )}
            </label>
            <select
              value={parameters.state ?? ""}
              onChange={(e) => update("state", e.target.value || null)}
              className="w-full p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-800 focus:outline-none focus:border-orange-500 cursor-pointer"
            >
              <option value="">{isHi ? "समस्त भारत (राष्ट्रीय योजनाएं)" : "All India (National Schemes)"}</option>
              <option value="Rajasthan">राजस्थान (Rajasthan)</option>
              <option value="Uttar Pradesh">उत्तर प्रदेश (Uttar Pradesh)</option>
              <option value="Maharashtra">महाराष्ट्र (Maharashtra)</option>
              <option value="Bihar">बिहार (Bihar)</option>
              <option value="Madhya Pradesh">मध्य प्रदेश (Madhya Pradesh)</option>
              <option value="West Bengal">पश्चिम बंगाल (West Bengal)</option>
              <option value="Gujarat">गुजरात (Gujarat)</option>
              <option value="Karnataka">कर्नाटक (Karnataka)</option>
              <option value="Tamil Nadu">तमिलनाडु (Tamil Nadu)</option>
              <option value="Andhra Pradesh">आंध्र प्रदेश (Andhra Pradesh)</option>
              <option value="Telangana">तेलंगाना (Telangana)</option>
              <option value="Kerala">केरल (Kerala)</option>
              <option value="Punjab">पंजाब (Punjab)</option>
              <option value="Haryana">हरियाणा (Haryana)</option>
              <option value="Delhi">दिल्ली NCR (Delhi)</option>
              <option value="Jharkhand">झारखंड (Jharkhand)</option>
              <option value="Odisha">ओडिशा (Odisha)</option>
              <option value="Assam">असम (Assam)</option>
              <option value="Chhattisgarh">छत्तीसगढ़ (Chhattisgarh)</option>
              <option value="Uttarakhand">उत्तराखंड (Uttarakhand)</option>
              <option value="Himachal Pradesh">हिमाचल प्रदेश (Himachal Pradesh)</option>
              <option value="Jammu & Kashmir">जम्मू एवं कश्मीर (Jammu & Kashmir)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className={`space-y-1 ${getHighlightClass("residence")}`}>
              <label className="font-bold text-slate-700 text-[11px]">
                {isHi ? "निवास क्षेत्र" : "Area"}
              </label>
              <div className="flex rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
                <button
                  type="button"
                  onClick={() => update("residence", "RURAL")}
                  className={`flex-1 py-1.5 text-[10px] font-bold cursor-pointer transition ${
                    parameters.residence === "RURAL" ? "bg-orange-600 text-white" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {isHi ? "ग्रामीण" : "Rural"}
                </button>
                <button
                  type="button"
                  onClick={() => update("residence", "URBAN")}
                  className={`flex-1 py-1.5 text-[10px] font-bold cursor-pointer transition ${
                    parameters.residence === "URBAN" ? "bg-orange-600 text-white" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {isHi ? "शहरी" : "Urban"}
                </button>
              </div>
            </div>

            <div className={`space-y-1 ${getHighlightClass("district")}`}>
              <label className="font-bold text-slate-700 text-[11px]">
                {isHi ? "गृह जिला / शहर" : "District / City"}
              </label>
              <input
                type="text"
                value={parameters.district ?? ""}
                onChange={(e) => update("district", e.target.value || null)}
                placeholder={isHi ? "जैसे: जयपुर, लखनऊ, पटना..." : "e.g. Jaipur, Lucknow..."}
                className="w-full p-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-medium text-slate-800 focus:outline-none focus:border-orange-500"
              />
            </div>
          </div>
        </div>

        {/* 7. Economic Card */}
        <div className={`space-y-1.5 ${getHighlightClass("rationCard")}`}>
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>💳</span>
              <span>{isHi ? "राशन कार्ड / आर्थिक श्रेणी" : "Ration Card / Tier"}</span>
              {highlightedField === "rationCard" && (
                <span className="text-[9px] text-amber-700 bg-amber-100 font-bold px-1.5 py-0.2 rounded-full animate-bounce">
                  ✨ {isHi ? "पहचाना गया" : "Detected"}
                </span>
              )}
            </label>
            {parameters.rationCard !== null && (
              <button
                type="button"
                onClick={() => update("rationCard", null)}
                className="text-[10px] text-slate-400 hover:text-slate-600 underline"
              >
                {isHi ? "हटाएं" : "Clear"}
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-1">
            {[
              { id: "AAY", label: "अंत्योदय (AAY)" },
              { id: "BPL", label: "BPL (बीपीएल)" },
              { id: "STATE_BPL", label: "State BPL" },
              { id: "NFSA", label: "खाद्य सुरक्षा" },
              { id: "NONE", label: "सामान्य (APL)" },
            ].map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => update("rationCard", r.id as any)}
                className={`py-1 px-1 rounded-lg border text-[10px] font-bold truncate transition cursor-pointer ${
                  parameters.rationCard === r.id
                    ? "bg-amber-600 text-white border-amber-600 shadow-xs ring-1 ring-amber-600"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* 8. Special Conditions (Widow, Disability, Land) */}
        <div className="space-y-2 pt-1 border-t border-slate-100">
          <label className="font-bold text-slate-700 text-[11px] block">
            {isHi ? "विशेष पात्रता शर्तें" : "Special Eligibility Conditions"}
          </label>

          {/* Disability Toggle */}
          <div className={`p-2 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5 ${getHighlightClass("isDisabled")}`}>
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700 flex items-center gap-1">
                <span>♿</span>
                <span>{isHi ? "दिव्यांग (विशेष योग्यजन)" : "Person with Disability"}</span>
              </span>
              <input
                type="checkbox"
                checked={parameters.isDisabled}
                onChange={(e) => update("isDisabled", e.target.checked)}
                className="w-4 h-4 accent-orange-600 rounded cursor-pointer"
              />
            </div>
            {parameters.isDisabled && (
              <div className="flex items-center justify-between text-[11px] text-slate-600 pt-1">
                <span>{isHi ? "दिव्यांगता प्रतिशत" : "Disability %"}:</span>
                <span className="font-bold text-orange-600">{parameters.disabilityPercent}%</span>
                <input
                  type="range"
                  min="40"
                  max="100"
                  value={parameters.disabilityPercent}
                  onChange={(e) => update("disabilityPercent", parseInt(e.target.value))}
                  className="w-24 accent-orange-600 cursor-pointer h-1 bg-slate-200"
                />
              </div>
            )}
          </div>

          {/* Widow Toggle */}
          <div className={`p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between ${getHighlightClass("isWidow")}`}>
            <span className="font-semibold text-slate-700 flex items-center gap-1">
              <span>👩</span>
              <span>{isHi ? "एकल नारी / विधवा / परित्यक्ता" : "Widow / Single Woman"}</span>
            </span>
            <input
              type="checkbox"
              checked={parameters.isWidow || parameters.maritalStatus === "WIDOW"}
              onChange={(e) => {
                const checked = e.target.checked;
                updateMany({
                  isWidow: checked,
                  maritalStatus: checked ? "WIDOW" : (parameters.maritalStatus === "WIDOW" ? null : parameters.maritalStatus),
                  ...(checked ? { gender: "FEMALE" } : {}),
                });
              }}
              className="w-4 h-4 accent-orange-600 rounded cursor-pointer"
            />
          </div>

          {/* Agricultural Land Bigha */}
          <div className={`p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between ${getHighlightClass("landBigha")}`}>
            <span className="font-semibold text-slate-700 flex items-center gap-1">
              <span>🌾</span>
              <span>{isHi ? "कृषि भूमि (बीघा)" : "Agricultural Land"}</span>
            </span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min="0"
                max="50"
                value={parameters.landBigha !== null ? parameters.landBigha : ""}
                placeholder="0"
                onChange={(e) => {
                  const val = e.target.value === "" ? null : Math.max(0, parseInt(e.target.value) || 0);
                  updateMany({
                    landBigha: val,
                    ...(val !== null && val > 0 && !parameters.occupation ? { occupation: "FARMER" } : {}),
                  });
                }}
                className="w-14 py-0.5 px-1.5 rounded bg-white border border-slate-300 font-bold text-slate-900 text-center text-xs"
              />
              <span className="text-[10px] text-slate-500">{isHi ? "बीघा" : "bigha"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Sticky Action Bar */}
      <div className="p-3 border-t border-slate-200 bg-slate-50 space-y-2">
        <button
          type="button"
          onClick={() => onApplyToChat(parameters)}
          className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 active:scale-98 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
        >
          <span>✨</span>
          <span>{isHi ? "इन मापदंडों से योजनाएं खोजें" : "Apply Parameters to Chat"}</span>
          <span>→</span>
        </button>
        <p className="text-[10px] text-center text-slate-400">
          {isHi
            ? "परिवर्तित जानकारी सीधे AI सहायक के संदर्भ में जुड़ जाएगी"
            : "Parameters dynamically injected into AI reasoning context"}
        </p>
      </div>
    </aside>
  );
}
