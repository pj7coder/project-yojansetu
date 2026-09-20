"use client";

import React from "react";

export interface PersonaData {
  id: string;
  name_en: string;
  name_hi: string;
  role_en: string;
  role_hi: string;
  district_en: string;
  district_hi: string;
  age: number;
  gender: string;
  income: number;
  land_bigha?: number;
  special_tags_en: string[];
  special_tags_hi: string[];
  avatar_emoji: string;
  query_en: string;
  query_hi: string;
  context: Record<string, any>;
}

export const PRESET_PERSONAS: PersonaData[] = [
  {
    id: "ram-devi",
    name_en: "Ram Devi",
    name_hi: "राम देवी",
    role_en: "Elderly Widow",
    role_hi: "वृद्ध विधवा",
    district_en: "Alwar",
    district_hi: "अलवर",
    age: 68,
    gender: "female",
    income: 40000,
    special_tags_en: ["Senior Citizen (68y)", "Widow", "Low Income"],
    special_tags_hi: ["वरिष्ठ नागरिक (68 वर्ष)", "विधवा", "कम आय"],
    avatar_emoji: "👵",
    query_en: "I am a 68-year-old widow from Alwar earning 40,000 per year. What monthly pension will I receive and what documents are required?",
    query_hi: "मैं अलवर की 68 साल की विधवा महिला हूँ और मेरी सालाना आय 40,000 है। मुझे कौनसी मासिक पेंशन मिलेगी और ई-मित्र पर क्या दस्तावेज लगेंगे?",
    context: {
      age: 68,
      gender: "FEMALE",
      marital_status: "WIDOWED",
      annual_income: 40000,
      district: "Alwar",
      has_jan_aadhaar: true,
    },
  },
  {
    id: "suraj-mal",
    name_en: "Suraj Mal",
    name_hi: "सूरज मल",
    role_en: "Small Farmer",
    role_hi: "लघु किसान",
    district_en: "Barmer",
    district_hi: "बाड़मेर",
    age: 45,
    gender: "male",
    income: 65000,
    land_bigha: 3.0,
    special_tags_en: ["Farmer (3 Bighas)", "Barmer", "PM-Kisan Eligible"],
    special_tags_hi: ["किसान (3 बीघा)", "बाड़मेर", "पीएम किसान पात्र"],
    avatar_emoji: "🌾",
    query_en: "I am a farmer in Barmer owning 3 bighas of land with income 65,000. Am I eligible for Rajasthan Kisan Samman Nidhi and DBT subsidy?",
    query_hi: "मैं बाड़मेर का किसान हूँ, मेरे पास 3 बीघा जमीन है और आय 65,000 है। क्या मुझे राजस्थान किसान सम्मान निधि और डीबीटी का लाभ मिलेगा?",
    context: {
      age: 45,
      gender: "MALE",
      occupation: "FARMER",
      land_area_bigha: 3.0,
      annual_income: 65000,
      district: "Barmer",
      has_jan_aadhaar: true,
    },
  },
  {
    id: "priya-sharma",
    name_en: "Priya Sharma",
    name_hi: "प्रिया शर्मा",
    role_en: "Meritorious Girl Student",
    role_hi: "मेधावी छात्रा",
    district_en: "Kota",
    district_hi: "कोटा",
    age: 18,
    gender: "female",
    income: 180000,
    special_tags_en: ["12th Board: 82%", "Kota", "Govt School"],
    special_tags_hi: ["12वीं बोर्ड: 82%", "कोटा", "सरकारी स्कूल"],
    avatar_emoji: "🎓",
    query_en: "I am an 18-year-old girl student from Kota scored 82% in 12th board from government school. Can I get a free scooty or Anuprati coaching?",
    query_hi: "मैं कोटा की 18 वर्षीय छात्रा हूँ, सरकारी स्कूल से 12वीं में 82% अंक आए हैं। क्या मुझे काली बाई स्कूटी या अनुप्रति कोचिंग मिल सकती है?",
    context: {
      age: 18,
      gender: "FEMALE",
      student_status: "ENROLLED",
      marks_percentage_12: 82.0,
      school_type: "GOVERNMENT",
      annual_income: 180000,
      district: "Kota",
      has_jan_aadhaar: true,
    },
  },
  {
    id: "mohan-lal",
    name_en: "Mohan Lal",
    name_hi: "मोहन लाल",
    role_en: "Divyang / Rural Laborer",
    role_hi: "दिव्यांग / ग्रामीण श्रमिक",
    district_en: "Sikar",
    district_hi: "सीकर",
    age: 36,
    gender: "male",
    income: 36000,
    special_tags_en: ["Divyang (40%+)", "BPL Family", "Health Card"],
    special_tags_hi: ["दिव्यांग (40%+)", "बीपीएल परिवार", "स्वास्थ्य कार्ड"],
    avatar_emoji: "♿",
    query_en: "I am a 36-year-old disabled citizen from Sikar with 45% disability and 36,000 income. What pension and free healthcare can I get?",
    query_hi: "मैं सीकर का 36 वर्षीय दिव्यांग नागरिक हूँ (45% दिव्यांगता) और आय 36,000 है। मुझे कौनसी विशेष योग्यजन पेंशन और स्वास्थ्य सुरक्षा मिलेगी?",
    context: {
      age: 36,
      gender: "MALE",
      is_disabled: true,
      disability_percentage: 45,
      annual_income: 36000,
      district: "Sikar",
      bpl_status: true,
      has_jan_aadhaar: true,
    },
  },
];

interface PersonaPickerProps {
  language: "hi" | "en";
  onSelectPersona: (persona: PersonaData) => void;
  selectedPersonaId?: string | null;
}

export function PersonaPicker({
  language,
  onSelectPersona,
  selectedPersonaId,
}: PersonaPickerProps) {
  const isHi = language === "hi";

  return (
    <div className="w-full bg-white/80 backdrop-blur-md border border-amber-200/80 rounded-2xl p-4 sm:p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">⚡</span>
          <div>
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              {isHi ? "त्वरित नागरिक परिदृश्य (1-क्लिक परीक्षण)" : "Quick Citizen Personas (1-Click Test)"}
            </h3>
            <p className="text-xs text-slate-500">
              {isHi
                ? "राजस्थान के वास्तविक नागरिकों के आधार पर तत्काल पात्रता एवं पेंशन का परीक्षण करें"
                : "Test live deterministic AST rules & gazetted circular matching instantly"}
            </p>
          </div>
        </div>
        <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200 self-start sm:self-center">
          {isHi ? "परीक्षक शॉर्टकट" : "Evaluator Preset"}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {PRESET_PERSONAS.map((p) => {
          const isSelected = selectedPersonaId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelectPersona(p)}
              className={`text-left p-3.5 rounded-xl border transition-all duration-200 group relative flex flex-col justify-between cursor-pointer ${
                isSelected
                  ? "bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/30 shadow-md scale-[1.01]"
                  : "bg-white hover:bg-slate-50 border-slate-200 hover:border-amber-300 shadow-xs hover:shadow"
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-1 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl p-1 bg-amber-50 rounded-lg border border-amber-100 group-hover:scale-110 transition-transform">
                      {p.avatar_emoji}
                    </span>
                    <div>
                      <div className="text-sm font-extrabold text-slate-900 leading-tight">
                        {isHi ? p.name_hi : p.name_en}
                      </div>
                      <div className="text-[11px] font-medium text-amber-800">
                        {isHi ? p.role_hi : p.role_en} • {isHi ? p.district_hi : p.district_en}
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-600 ring-4 ring-amber-100" />
                  )}
                </div>

                <div className="flex flex-wrap gap-1 mb-2">
                  {(isHi ? p.special_tags_hi : p.special_tags_en).map((tag, idx) => (
                    <span
                      key={idx}
                      className="text-[10px] font-medium bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200/60"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-semibold text-amber-700 group-hover:text-amber-800">
                <span>{isHi ? "जाँचें →" : "Evaluate →"}</span>
                <span className="text-slate-400 font-mono text-[10px]">
                  ₹{p.income.toLocaleString("en-IN")}/yr
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default PersonaPicker;
