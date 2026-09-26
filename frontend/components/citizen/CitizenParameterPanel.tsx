"use client";

import React, { useState, useEffect } from "react";
import { RajasthanDistrictItem } from "../../types/citizen";
import { getRajasthanDistricts } from "../../lib/api";

export interface CitizenParameters {
  age: number;
  gender: "MALE" | "FEMALE" | "OTHER";
  category: "GENERAL" | "OBC" | "SC" | "ST" | "EWS" | "MBC";
  income: number;
  occupation: string;
  residence: "RURAL" | "URBAN";
  district: string;
  rationCard: "NONE" | "BPL" | "STATE_BPL" | "AAY" | "NFSA";
  isWidow: boolean;
  isDisabled: boolean;
  disabilityPercent: number;
  landBigha: number;
  hasJanAadhaar: boolean;
  isStudent: boolean;
  maritalStatus: "MARRIED" | "SINGLE" | "WIDOW" | "DIVORCED";
}

export const DEFAULT_CITIZEN_PARAMETERS: CitizenParameters = {
  age: 45,
  gender: "FEMALE",
  category: "OBC",
  income: 120000,
  occupation: "FARMER",
  residence: "RURAL",
  district: "Jaipur",
  rationCard: "BPL",
  isWidow: false,
  isDisabled: false,
  disabilityPercent: 40,
  landBigha: 2,
  hasJanAadhaar: true,
  isStudent: false,
  maritalStatus: "MARRIED",
};

interface CitizenParameterPanelProps {
  parameters: CitizenParameters;
  onChange: (newParams: CitizenParameters) => void;
  onApplyToChat: (params: CitizenParameters) => void;
  lang: "hi" | "en";
  isOpen?: boolean;
  onClose?: () => void;
}

export function CitizenParameterPanel({
  parameters,
  onChange,
  onApplyToChat,
  lang = "hi",
  isOpen = true,
  onClose,
}: CitizenParameterPanelProps) {
  const isHi = lang === "hi";
  const [districts, setDistricts] = useState<RajasthanDistrictItem[]>([]);

  useEffect(() => {
    getRajasthanDistricts()
      .then((data) => setDistricts(data))
      .catch(() => {});
  }, []);

  const update = <K extends keyof CitizenParameters>(key: K, val: CitizenParameters[K]) => {
    onChange({
      ...parameters,
      [key]: val,
    });
  };

  // Quick 1-click Preset Personas
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
              {isHi ? "अपनी जानकारी अनुकूलित करें" : "Customize profile details"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onChange(DEFAULT_CITIZEN_PARAMETERS)}
            title={isHi ? "रीसेट करें" : "Reset defaults"}
            className="px-2 py-1 text-[11px] font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-md hover:bg-slate-100 transition"
          >
            {isHi ? "रीसेट" : "Reset"}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="lg:hidden p-1 rounded hover:bg-slate-200 text-slate-500 text-sm"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Preset Personas Row */}
      <div className="p-2.5 bg-orange-50/60 border-b border-orange-100">
        <div className="text-[10px] font-black text-orange-800 uppercase tracking-wide mb-1.5 flex items-center justify-between">
          <span>{isHi ? "त्वरित प्रोफाइल चुनें" : "Quick 1-Click Profiles"}</span>
          <span className="text-[9px] text-orange-600">Preset</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={() => applyPreset("FARMER")}
            className="p-1.5 rounded-lg bg-white border border-orange-200 hover:border-orange-400 text-left transition shadow-2xs cursor-pointer"
          >
            <div className="text-[11px] font-bold text-slate-800">🌾 {isHi ? "किसान" : "Farmer"}</div>
            <div className="text-[9px] text-slate-500">48 yr • BPL • 3 बीघा</div>
          </button>
          <button
            type="button"
            onClick={() => applyPreset("SENIOR")}
            className="p-1.5 rounded-lg bg-white border border-orange-200 hover:border-orange-400 text-left transition shadow-2xs cursor-pointer"
          >
            <div className="text-[11px] font-bold text-slate-800">👴 {isHi ? "वृद्ध नागरिक" : "Senior"}</div>
            <div className="text-[9px] text-slate-500">65 yr • AAY • SC</div>
          </button>
          <button
            type="button"
            onClick={() => applyPreset("STUDENT")}
            className="p-1.5 rounded-lg bg-white border border-orange-200 hover:border-orange-400 text-left transition shadow-2xs cursor-pointer"
          >
            <div className="text-[11px] font-bold text-slate-800">🎓 {isHi ? "विद्यार्थी" : "Student"}</div>
            <div className="text-[9px] text-slate-500">20 yr • ST • Udaipur</div>
          </button>
          <button
            type="button"
            onClick={() => applyPreset("WIDOW")}
            className="p-1.5 rounded-lg bg-white border border-orange-200 hover:border-orange-400 text-left transition shadow-2xs cursor-pointer"
          >
            <div className="text-[11px] font-bold text-slate-800">👩 {isHi ? "महिला/विधवा" : "Widow"}</div>
            <div className="text-[9px] text-slate-500">52 yr • Pension</div>
          </button>
        </div>
      </div>

      {/* Main Parameters Form */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4 text-xs scrollbar-thin">
        {/* 1. Age */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>🎂</span>
              <span>{isHi ? "आयु (वर्ष)" : "Age (Years)"}</span>
            </label>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => update("age", Math.max(1, parameters.age - 1))}
                className="w-5 h-5 rounded bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 hover:bg-slate-200"
              >
                -
              </button>
              <span className="font-black text-slate-900 w-8 text-center bg-slate-50 py-0.5 rounded border border-slate-200">
                {parameters.age}
              </span>
              <button
                type="button"
                onClick={() => update("age", Math.min(100, parameters.age + 1))}
                className="w-5 h-5 rounded bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 hover:bg-slate-200"
              >
                +
              </button>
            </div>
          </div>
          <input
            type="range"
            min="10"
            max="95"
            value={parameters.age}
            onChange={(e) => update("age", parseInt(e.target.value))}
            className="w-full accent-orange-600 cursor-pointer h-1.5 bg-slate-200 rounded-lg"
          />
        </div>

        {/* 2. Gender */}
        <div className="space-y-1.5">
          <label className="font-bold text-slate-700 flex items-center gap-1">
            <span>⚧️</span>
            <span>{isHi ? "लिंग" : "Gender"}</span>
          </label>
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
                  update("gender", g.id as any);
                  if (g.id !== "FEMALE") {
                    update("isWidow", false);
                    if (parameters.maritalStatus === "WIDOW") {
                      update("maritalStatus", "MARRIED");
                    }
                  }
                }}
                className={`py-1.5 px-2 rounded-md font-bold text-[11px] transition ${
                  parameters.gender === g.id
                    ? "bg-white text-orange-600 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {isHi ? g.hi : g.en}
              </button>
            ))}
          </div>
        </div>

        {/* 3. Social Category */}
        <div className="space-y-1.5">
          <label className="font-bold text-slate-700 flex items-center gap-1">
            <span>🏷️</span>
            <span>{isHi ? "जाति श्रेणी" : "Social Category"}</span>
          </label>
          <div className="grid grid-cols-3 gap-1">
            {(["GENERAL", "OBC", "SC", "ST", "EWS", "MBC"] as const).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => update("category", cat)}
                className={`py-1 rounded-lg border text-[11px] font-bold transition ${
                  parameters.category === cat
                    ? "bg-orange-600 text-white border-orange-600 shadow-xs"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* 4. Annual Income */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="font-bold text-slate-700 flex items-center gap-1">
              <span>💰</span>
              <span>{isHi ? "वार्षिक पारिवारिक आय" : "Annual Income"}</span>
            </label>
            <span className="font-black text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-[11px]">
              ₹{parameters.income.toLocaleString("en-IN")}
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
                className={`py-1 rounded border text-[10px] font-bold transition ${
                  parameters.income === p.val
                    ? "bg-emerald-600 text-white border-emerald-600"
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
            value={parameters.income}
            onChange={(e) => update("income", parseInt(e.target.value) || 0)}
            className="w-full accent-emerald-600 cursor-pointer h-1.5 bg-slate-200 rounded-lg mt-1"
          />
        </div>

        {/* 5. Occupation */}
        <div className="space-y-1.5">
          <label className="font-bold text-slate-700 flex items-center gap-1">
            <span>💼</span>
            <span>{isHi ? "व्यवसाय / कार्य" : "Occupation"}</span>
          </label>
          <select
            value={parameters.occupation}
            onChange={(e) => {
              const occ = e.target.value;
              update("occupation", occ);
              if (occ === "STUDENT") update("isStudent", true);
              else update("isStudent", false);
            }}
            className="w-full p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-medium text-slate-800 focus:outline-none focus:border-orange-500"
          >
            <option value="FARMER">{isHi ? "कृषक / किसान (Farmer)" : "Farmer"}</option>
            <option value="LABORER">{isHi ? "दिहाड़ी श्रमिक / मजदूर (Daily Wage)" : "Laborer / Daily Wage"}</option>
            <option value="STUDENT">{isHi ? "विद्यार्थी / छात्र (Student)" : "Student"}</option>
            <option value="SELF_EMPLOYED">{isHi ? "स्वरोजगार / छोटा व्यापारी (Self Employed)" : "Self Employed"}</option>
            <option value="HOMEMAKER">{isHi ? "गृहणी (Homemaker)" : "Homemaker"}</option>
            <option value="UNEMPLOYED">{isHi ? "बेरोजगार युवा (Unemployed)" : "Unemployed"}</option>
            <option value="RETIRED">{isHi ? "वरिष्ठ / सेवानिवृत्त (Retired)" : "Retired"}</option>
          </select>
        </div>

        {/* 6. Residence & District */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label className="font-bold text-slate-700 text-[11px]">
              {isHi ? "निवास क्षेत्र" : "Area"}
            </label>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
              <button
                type="button"
                onClick={() => update("residence", "RURAL")}
                className={`flex-1 py-1.5 text-[10px] font-bold ${
                  parameters.residence === "RURAL" ? "bg-orange-600 text-white" : "text-slate-600"
                }`}
              >
                {isHi ? "ग्रामीण" : "Rural"}
              </button>
              <button
                type="button"
                onClick={() => update("residence", "URBAN")}
                className={`flex-1 py-1.5 text-[10px] font-bold ${
                  parameters.residence === "URBAN" ? "bg-orange-600 text-white" : "text-slate-600"
                }`}
              >
                {isHi ? "शहरी" : "Urban"}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="font-bold text-slate-700 text-[11px]">
              {isHi ? "गृह जिला" : "District"}
            </label>
            <select
              value={parameters.district}
              onChange={(e) => update("district", e.target.value)}
              className="w-full p-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-medium text-slate-800 focus:outline-none focus:border-orange-500"
            >
              {districts.length > 0 ? (
                districts.map((d) => (
                  <option key={d.name_en} value={d.name_en}>
                    {isHi ? d.name_hi : d.name_en}
                  </option>
                ))
              ) : (
                <>
                  <option value="Jaipur">जयपुर (Jaipur)</option>
                  <option value="Jodhpur">जोधपुर (Jodhpur)</option>
                  <option value="Udaipur">उदयपुर (Udaipur)</option>
                  <option value="Kota">कोटा (Kota)</option>
                  <option value="Bikaner">बीकानेर (Bikaner)</option>
                  <option value="Ajmer">अजमेर (Ajmer)</option>
                  <option value="Alwar">अलवर (Alwar)</option>
                </>
              )}
            </select>
          </div>
        </div>

        {/* 7. Economic Card */}
        <div className="space-y-1.5">
          <label className="font-bold text-slate-700 flex items-center gap-1">
            <span>💳</span>
            <span>{isHi ? "राशन कार्ड / आर्थिक श्रेणी" : "Ration Card / Tier"}</span>
          </label>
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
                className={`py-1 px-1 rounded-lg border text-[10px] font-bold truncate transition ${
                  parameters.rationCard === r.id
                    ? "bg-amber-600 text-white border-amber-600 shadow-xs"
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
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5">
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

          {/* Widow Toggle (if female) */}
          {parameters.gender === "FEMALE" && (
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
              <span className="font-semibold text-slate-700 flex items-center gap-1">
                <span>👩</span>
                <span>{isHi ? "एकल नारी / विधवा / परित्यक्ता" : "Widow / Single Woman"}</span>
              </span>
              <input
                type="checkbox"
                checked={parameters.isWidow || parameters.maritalStatus === "WIDOW"}
                onChange={(e) => {
                  update("isWidow", e.target.checked);
                  update("maritalStatus", e.target.checked ? "WIDOW" : "MARRIED");
                }}
                className="w-4 h-4 accent-orange-600 rounded cursor-pointer"
              />
            </div>
          )}

          {/* Agricultural Land Bigha */}
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
            <span className="font-semibold text-slate-700 flex items-center gap-1">
              <span>🌾</span>
              <span>{isHi ? "कृषि भूमि (बीघा)" : "Agricultural Land"}</span>
            </span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min="0"
                max="50"
                value={parameters.landBigha}
                onChange={(e) => update("landBigha", Math.max(0, parseInt(e.target.value) || 0))}
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
