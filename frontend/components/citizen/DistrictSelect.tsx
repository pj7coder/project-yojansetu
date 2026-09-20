"use client";

import React, { useEffect, useState } from "react";
import { CitizenQuestionDisplay, RajasthanDistrictItem } from "../../types/citizen";
import { getRajasthanDistricts } from "../../lib/api";

interface DistrictSelectProps {
  question: CitizenQuestionDisplay;
  lang: "hi" | "en";
  onSubmit: (districtName: string) => void;
  onDecline: () => void;
  isSubmitting: boolean;
}

export function DistrictSelect({
  question,
  lang,
  onSubmit,
  onDecline,
  isSubmitting,
}: DistrictSelectProps) {
  const [districts, setDistricts] = useState<RajasthanDistrictItem[]>([]);
  const [searchFilter, setSearchFilter] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState<string>("");
  const [loadingDistricts, setLoadingDistricts] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const data = await getRajasthanDistricts();
        if (isMounted) {
          setDistricts(data);
          setLoadingDistricts(false);
        }
      } catch (err) {
        if (isMounted) {
          setLoadingDistricts(false);
        }
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const filteredDistricts = districts.filter((d) => {
    if (!searchFilter.trim()) return true;
    const term = searchFilter.toLowerCase().trim();
    return (
      d.name_en.toLowerCase().includes(term) ||
      d.name_hi.toLowerCase().includes(term) ||
      d.aliases.some((a) => a.toLowerCase().includes(term))
    );
  });

  const handleSelectAndSubmit = (nameEn: string) => {
    setSelectedDistrict(nameEn);
    onSubmit(nameEn);
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1 text-left">
        <label
          htmlFor="input-district-search"
          className="block text-sm font-semibold text-slate-700"
        >
          {lang === "hi"
            ? "राजस्थान के जिले का चयन करें"
            : "Select your Rajasthan district"}
        </label>
        <p className="text-xs text-slate-500">
          {lang === "hi"
            ? "खोजने के लिए जिले का नाम टाइप करें या सूची में से चुनें"
            : "Type district name to search or choose from the list below"}
        </p>
      </div>

      {/* Search Input */}
      <div className="relative">
        <input
          id="input-district-search"
          type="text"
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          placeholder={
            lang === "hi"
              ? "जिला खोजें (जैसे: उदयपुर, जयपुर, जोधपुर)…"
              : "Search district (e.g. Udaipur, Jaipur, Jodhpur)…"
          }
          className="w-full px-4 py-2.5 text-sm text-slate-900 bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-all shadow-inner"
        />
        {searchFilter && (
          <button
            type="button"
            onClick={() => setSearchFilter("")}
            className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        )}
      </div>

      {/* District List */}
      <div className="max-h-56 overflow-y-auto border border-slate-200 rounded-xl bg-slate-50/50 divide-y divide-slate-200/60 shadow-inner">
        {loadingDistricts ? (
          <div className="p-4 text-xs text-slate-500 text-center">
            {lang === "hi"
              ? "जिलों की सूची लोड हो रही है…"
              : "Loading district registry…"}
          </div>
        ) : filteredDistricts.length === 0 ? (
          <div className="p-4 text-xs text-slate-500 text-center">
            {lang === "hi"
              ? "कोई जिला नहीं मिला। कृपया वर्तनी जाँचें।"
              : "No district found matching search."}
          </div>
        ) : (
          filteredDistricts.map((d) => {
            const isSelected = selectedDistrict === d.name_en;
            return (
              <button
                key={d.code}
                type="button"
                id={`dist-${d.code.toLowerCase()}`}
                onClick={() => handleSelectAndSubmit(d.name_en)}
                disabled={isSubmitting}
                className={`w-full px-4 py-2.5 text-left flex items-center justify-between text-sm transition-colors ${
                  isSelected
                    ? "bg-orange-100 text-orange-900 font-bold"
                    : "hover:bg-white text-slate-800"
                }`}
              >
                <span>
                  <span className="font-semibold">
                    {lang === "hi" ? d.name_hi : d.name_en}
                  </span>
                  <span className="text-xs text-slate-500 ml-2">
                    ({lang === "hi" ? d.name_en : d.name_hi})
                  </span>
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {d.code}
                </span>
              </button>
            );
          })
        )}
      </div>

      {/* Decline action */}
      {question.allow_decline && (
        <div className="pt-2 text-center sm:text-left">
          <button
            type="button"
            id="btn-decline-district"
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

export default DistrictSelect;
