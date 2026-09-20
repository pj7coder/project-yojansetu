"use client";

import React, { useState, useMemo } from "react";

interface SimulatorProps {
  language: "hi" | "en";
  onApplyToAgent: (params: {
    age: number;
    income: number;
    landBigha: number;
    category: string;
    gender: string;
    isWidow: boolean;
    isStudent: boolean;
    isDisabled: boolean;
    hasJanAadhaar: boolean;
  }) => void;
}

export function EligibilitySimulator({ language, onApplyToAgent }: SimulatorProps) {
  const isHi = language === "hi";

  // Simulator state
  const [age, setAge] = useState<number>(62);
  const [income, setIncome] = useState<number>(45000);
  const [landBigha, setLandBigha] = useState<number>(0);
  const [gender, setGender] = useState<"FEMALE" | "MALE">("FEMALE");
  const [category, setCategory] = useState<string>("OBC");
  const [isWidow, setIsWidow] = useState<boolean>(false);
  const [isStudent, setIsStudent] = useState<boolean>(false);
  const [isDisabled, setIsDisabled] = useState<boolean>(false);
  const [hasJanAadhaar, setHasJanAadhaar] = useState<boolean>(true);

  // Real-time live deterministic scheme estimation based on authentic Rajasthan rules
  const simulationResults = useMemo(() => {
    const eligible: Array<{
      code: string;
      title_hi: string;
      title_en: string;
      payout_hi: string;
      payout_en: string;
      est_annual: number;
      category_tag: string;
    }> = [];

    // 1. Mukhyamantri Vridhjan Samman Pension
    // Female >= 55 or Male >= 58, Income <= 48,000
    const ageEligible = (gender === "FEMALE" && age >= 55) || (gender === "MALE" && age >= 58);
    if (ageEligible && income <= 48000) {
      const monthly = age >= 75 ? 1500 : 1000;
      eligible.push({
        code: "RJ-PENSION-VRIDHJAN",
        title_hi: "मुख्यमंत्री वृद्धजन सम्मान पेंशन",
        title_en: "Mukhyamantri Vridhjan Samman Pension",
        payout_hi: `₹${monthly}/माह (${age >= 75 ? "75+ वर्ष स्लैब" : "सामान्य स्लैब"})`,
        payout_en: `₹${monthly}/mo (${age >= 75 ? "75+ Slab" : "Standard Slab"})`,
        est_annual: monthly * 12,
        category_tag: "Social Security",
      });
    }

    // 2. Mukhyamantri Ekal Nari Pension
    if (gender === "FEMALE" && isWidow && age >= 18 && income <= 48000) {
      let monthly = 1000;
      if (age >= 75) monthly = 1500;
      else if (age >= 60) monthly = 1250;
      eligible.push({
        code: "RJ-PENSION-EKAL-NARI",
        title_hi: "मुख्यमंत्री एकल नारी सम्मान पेंशन",
        title_en: "Mukhyamantri Ekal Nari Samman Pension",
        payout_hi: `₹${monthly}/माह`,
        payout_en: `₹${monthly}/mo`,
        est_annual: monthly * 12,
        category_tag: "Women Welfare",
      });
    }

    // 3. Rajasthan Kisan Samman Nidhi + PM-Kisan
    if (landBigha > 0 && landBigha <= 20) {
      eligible.push({
        code: "RJ-AGRI-KISAN-SAMMAN",
        title_hi: "राजस्थान किसान सम्मान निधि योजना",
        title_en: "Rajasthan Kisan Samman Nidhi Scheme",
        payout_hi: "₹8,000/वर्ष (₹6,000 केंद्र + ₹2,000 राज्य)",
        payout_en: "₹8,000/yr (₹6,000 PM + ₹2,000 State)",
        est_annual: 8000,
        category_tag: "Agriculture",
      });
    }

    // 4. Mukhyamantri Ayushman Arogya (Maa) Health Insurance
    if (income <= 200000 || hasJanAadhaar) {
      eligible.push({
        code: "RJ-HEALTH-MAA",
        title_hi: "मुख्यमंत्री आयुष्मान आरोग्य योजना (MAA)",
        title_en: "Mukhyamantri Ayushman Arogya (MAA) Yojana",
        payout_hi: "₹25 लाख कैशलेस स्वास्थ्य बीमा",
        payout_en: "₹25 Lakh Cashless Health Cover",
        est_annual: 25000, // Notional insurance value
        category_tag: "Healthcare",
      });
    }

    // 5. Kali Bai Bheel Scooty Scheme (Girl students 18-24 with high marks)
    if (gender === "FEMALE" && isStudent && age >= 17 && age <= 24 && income <= 250000) {
      eligible.push({
        code: "RJ-EDU-KALI-BAI-SCOOTY",
        title_hi: "काली बाई भील मेधावी छात्रा स्कूटी योजना",
        title_en: "Kali Bai Bheel Medhavi Chhatra Scooty Yojana",
        payout_hi: "निःशुल्क मोटर स्कूटी + हेलमेट (₹85,000 मान)",
        payout_en: "Free Motorized Scooty + Helmet (Value ₹85,000)",
        est_annual: 85000,
        category_tag: "Education",
      });
    }

    // 6. Mukhyamantri Anuprati Coaching Scheme
    if (isStudent && age >= 16 && age <= 28 && income <= 250000) {
      eligible.push({
        code: "RJ-EDU-ANUPRATI",
        title_hi: "मुख्यमंत्री अनुप्रति कोचिंग योजना",
        title_en: "Mukhyamantri Anuprati Coaching Yojana",
        payout_hi: "100% निःशुल्क कोचिंग + ₹40,000 आवास भत्ता",
        payout_en: "100% Free Coaching + ₹40,000 Hostel Allowance",
        est_annual: 60000,
        category_tag: "Youth",
      });
    }

    // 7. Vishesh Yogyajan (Divyang) Pension
    if (isDisabled && income <= 60000) {
      let monthly = 1000;
      if (age >= 75) monthly = 1500;
      else if (age >= 60) monthly = 1250;
      eligible.push({
        code: "RJ-SJE-DIVYANG-PENSION",
        title_hi: "राजस्थान विशेष योग्यजन सम्मान पेंशन",
        title_en: "Rajasthan Vishesh Yogyajan Pension",
        payout_hi: `₹${monthly}/माह (40%+ दिव्यांगता)`,
        payout_en: `₹${monthly}/mo (40%+ Disability)`,
        est_annual: monthly * 12,
        category_tag: "Disability Welfare",
      });
    }

    // 8. Rasoi Gas Cylinder Subsidy
    if (income <= 100000) {
      eligible.push({
        code: "RJ-CIVIL-GAS-SUBSIDY",
        title_hi: "मुख्यमंत्री रसोई गैस सिलेंडर सब्सिडी योजना",
        title_en: "CM Cooking Gas Cylinder Subsidy Scheme",
        payout_hi: "₹450 में गैस सिलेंडर (प्रति माह ₹400+ बचत)",
        payout_en: "Cylinder at ₹450 (Save ₹400+/month)",
        est_annual: 4800,
        category_tag: "Civil Supplies",
      });
    }

    const totalCashBenefit = eligible
      .filter((s) => s.code.includes("PENSION") || s.code.includes("KISAN") || s.code.includes("SUBSIDY"))
      .reduce((sum, item) => sum + item.est_annual, 0);

    return {
      eligible,
      totalCount: eligible.length,
      totalCashBenefit,
    };
  }, [age, income, landBigha, gender, category, isWidow, isStudent, isDisabled, hasJanAadhaar]);

  const handleApply = () => {
    onApplyToAgent({
      age,
      income,
      landBigha,
      category,
      gender,
      isWidow,
      isStudent,
      isDisabled,
      hasJanAadhaar,
    });
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-linear-to-r from-orange-600 via-amber-600 to-yellow-600 text-white p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/20 backdrop-blur-xs text-[11px] font-bold text-white mb-1.5 uppercase tracking-wide">
              <span>🎛️</span>
              <span>{isHi ? "लाइव पात्रता सिम्युलेटर" : "Live Eligibility Simulator"}</span>
            </div>
            <h3 className="text-base sm:text-lg font-black tracking-tight leading-snug">
              {isHi
                ? "स्लाइडर घुमाएँ और सरकारी लाभ तुरंत देखें"
                : "Adjust Sliders & See Instant Government Benefits"}
            </h3>
            <p className="text-xs text-orange-100 font-medium">
              {isHi
                ? "100% प्रामाणिक नियम • वास्तविक समय पर पेंशन व अनुदान की गणना"
                : "Pure deterministic evaluation • Zero guesswork"}
            </p>
          </div>

          <div className="text-right hidden sm:block">
            <div className="text-2xl font-black">{simulationResults.totalCount}</div>
            <div className="text-[11px] text-orange-100 font-semibold">
              {isHi ? "पात्र योजनाएं" : "Eligible Schemes"}
            </div>
          </div>
        </div>
      </div>

      <div className="p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Sliders & Controls (7 Cols) */}
        <div className="lg:col-span-7 space-y-5">
          {/* Gender & Category Toggle */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                {isHi ? "लिंग (Gender)" : "Gender"}
              </label>
              <div className="grid grid-cols-2 gap-1.5 bg-slate-100 p-1 rounded-xl">
                <button
                  type="button"
                  onClick={() => {
                    setGender("FEMALE");
                  }}
                  className={`py-1.5 text-xs font-bold rounded-lg transition-all ${
                    gender === "FEMALE"
                      ? "bg-white text-orange-700 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {isHi ? "महिला" : "Female"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setGender("MALE");
                    setIsWidow(false);
                  }}
                  className={`py-1.5 text-xs font-bold rounded-lg transition-all ${
                    gender === "MALE"
                      ? "bg-white text-orange-700 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {isHi ? "पुरुष" : "Male"}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                {isHi ? "सामाजिक वर्ग (Category)" : "Category"}
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full text-xs font-bold bg-slate-100 border border-slate-200 rounded-xl p-2 text-slate-800 focus:ring-2 focus:ring-orange-500 focus:outline-hidden"
              >
                <option value="GEN">General (सामान्य)</option>
                <option value="OBC">OBC (अन्य पिछड़ा वर्ग)</option>
                <option value="SC">SC (अनुसूचित जाति)</option>
                <option value="ST">ST (अनुसूचित जनजाति)</option>
                <option value="EWS">EWS (आर्थिक कमजोर)</option>
              </select>
            </div>
          </div>

          {/* Age Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-bold text-slate-700">
                {isHi ? "उम्र (Age)" : "Age"}:{" "}
                <span className="text-orange-700 font-extrabold text-sm font-mono">{age}</span>{" "}
                {isHi ? "वर्ष" : "years"}
              </span>
              <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                {age >= 75
                  ? isHi
                    ? "वरिष्ठ (75+ स्लैब: ₹1500)"
                    : "75+ Slab (₹1,500/mo)"
                  : age >= 60
                  ? isHi
                    ? "वरिष्ठ नागरिक (₹1000)"
                    : "Senior (₹1,000/mo)"
                  : isHi
                  ? "युवा / वयस्क"
                  : "Adult / Youth"}
              </span>
            </div>
            <input
              type="range"
              min="16"
              max="90"
              value={age}
              onChange={(e) => setAge(parseInt(e.target.value))}
              className="w-full accent-orange-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono mt-0.5">
              <span>16 yr</span>
              <span>55 yr (महिला पेंशन)</span>
              <span>58 yr (पुरुष पेंशन)</span>
              <span>75 yr (अधिकतम स्लैब)</span>
              <span>90 yr</span>
            </div>
          </div>

          {/* Income Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-bold text-slate-700">
                {isHi ? "वार्षिक आय (Annual Income)" : "Annual Income"}:{" "}
                <span className="text-orange-700 font-extrabold text-sm font-mono">
                  ₹{income.toLocaleString("en-IN")}
                </span>
                /yr
              </span>
              <span
                className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
                  income <= 48000
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {income <= 48000
                  ? isHi
                    ? "पेंशन सीमा के भीतर (≤ ₹48,000)"
                    : "Pension Income Cap OK"
                  : isHi
                  ? "सामान्य आय"
                  : "Standard Income"}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="250000"
              step="5000"
              value={income}
              onChange={(e) => setIncome(parseInt(e.target.value))}
              className="w-full accent-orange-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono mt-0.5">
              <span>₹0</span>
              <span>₹48K (पेंशन सीमा)</span>
              <span>₹1 Lakh</span>
              <span>₹2.5 Lakh (अनुप्रति सीमा)</span>
            </div>
          </div>

          {/* Land Holding Slider */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-bold text-slate-700">
                {isHi ? "कृषि भूमि (Agricultural Land)" : "Land Holding"}:{" "}
                <span className="text-orange-700 font-extrabold text-sm font-mono">{landBigha}</span>{" "}
                {isHi ? "बीघा" : "Bighas"}
              </span>
              <span
                className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
                  landBigha > 0 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-500"
                }`}
              >
                {landBigha > 0 && landBigha <= 5
                  ? isHi
                    ? "लघु / सीमांत किसान"
                    : "Small/Marginal Farmer"
                  : landBigha > 5
                  ? isHi
                    ? "किसान"
                    : "Farmer"
                  : isHi
                  ? "गैर-कृषक"
                  : "Non-Farmer"}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="0.5"
              value={landBigha}
              onChange={(e) => setLandBigha(parseFloat(e.target.value))}
              className="w-full accent-orange-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400 font-mono mt-0.5">
              <span>0 बीघा</span>
              <span>3 बीघा</span>
              <span>5 बीघा</span>
              <span>10 बीघा</span>
              <span>20 बीघा</span>
            </div>
          </div>

          {/* Quick Condition Checkbox Badges */}
          <div className="pt-2 border-t border-slate-200/80">
            <span className="text-xs font-bold text-slate-700 block mb-2">
              {isHi ? "विशेष पात्रता फ़्लैग (Special Status Tags)" : "Special Status Badges"}
            </span>
            <div className="flex flex-wrap gap-2">
              {gender === "FEMALE" && (
                <button
                  type="button"
                  onClick={() => setIsWidow(!isWidow)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors cursor-pointer ${
                    isWidow
                      ? "bg-rose-100 text-rose-800 border-rose-300 ring-1 ring-rose-300"
                      : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
                  }`}
                >
                  {isHi ? "विधवा (Widow)" : "Widow"} {isWidow ? "✓" : "+"}
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsStudent(!isStudent)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors cursor-pointer ${
                  isStudent
                    ? "bg-blue-100 text-blue-800 border-blue-300 ring-1 ring-blue-300"
                    : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
                }`}
              >
                {isHi ? "विद्यार्थी (Student)" : "Student"} {isStudent ? "✓" : "+"}
              </button>

              <button
                type="button"
                onClick={() => setIsDisabled(!isDisabled)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors cursor-pointer ${
                  isDisabled
                    ? "bg-purple-100 text-purple-800 border-purple-300 ring-1 ring-purple-300"
                    : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
                }`}
              >
                {isHi ? "दिव्यांग (Divyang 40%+)" : "Differently Abled"} {isDisabled ? "✓" : "+"}
              </button>

              <button
                type="button"
                onClick={() => setHasJanAadhaar(!hasJanAadhaar)}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors cursor-pointer ${
                  hasJanAadhaar
                    ? "bg-emerald-100 text-emerald-800 border-emerald-300 ring-1 ring-emerald-300"
                    : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
                }`}
              >
                {isHi ? "जन आधार कार्ड (Jan Aadhaar)" : "Jan Aadhaar Card"} {hasJanAadhaar ? "✓" : "+"}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Live Dynamic Scheme Matches (5 Cols) */}
        <div className="lg:col-span-5 flex flex-col justify-between bg-slate-50 rounded-xl p-4 border border-slate-200">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                {isHi ? "तात्कालिक पात्रता गणना" : "Live Eligibility Output"}
              </span>
              <span className="text-xs font-black text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full">
                {simulationResults.totalCount} {isHi ? "योजनाएं" : "Schemes"}
              </span>
            </div>

            {/* Estimated Annual Direct Benefit Callout */}
            {simulationResults.totalCashBenefit > 0 && (
              <div className="mb-3 p-3 bg-linear-to-br from-emerald-500/10 to-teal-500/10 border border-emerald-300 rounded-xl">
                <div className="text-[11px] font-bold text-emerald-900">
                  {isHi ? "अनुमानित वार्षिक प्रत्यक्ष डीबीटी लाभ" : "Estimated Annual Direct Cash Benefit"}
                </div>
                <div className="text-xl font-black text-emerald-700 font-mono">
                  ₹{simulationResults.totalCashBenefit.toLocaleString("en-IN")}
                  <span className="text-xs font-normal text-emerald-800 ml-1">/year</span>
                </div>
              </div>
            )}

            {/* Schemes List with real payout tags */}
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {simulationResults.eligible.map((item) => (
                <div
                  key={item.code}
                  className="p-2.5 bg-white rounded-lg border border-slate-200 text-left shadow-2xs hover:border-orange-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-1">
                    <span className="text-xs font-bold text-slate-900 leading-tight">
                      {isHi ? item.title_hi : item.title_en}
                    </span>
                    <span className="text-[10px] font-bold text-orange-700 bg-orange-50 px-1.5 py-0.2 rounded shrink-0">
                      {item.category_tag}
                    </span>
                  </div>
                  <div className="text-[11px] font-extrabold text-emerald-700 mt-1">
                    {isHi ? item.payout_hi : item.payout_en}
                  </div>
                </div>
              ))}

              {simulationResults.eligible.length === 0 && (
                <div className="py-8 text-center text-xs text-slate-400">
                  {isHi
                    ? "दी गई शर्तों में कोई सीधी योजना नहीं मिली। कृपया आय अथवा उम्र समायोजित करें।"
                    : "No direct schemes match these exact filters. Try adjusting age or income."}
                </div>
              )}
            </div>
          </div>

          {/* Action Button: Feed parameters into ReAct Agent */}
          <div className="mt-4 pt-3 border-t border-slate-200">
            <button
              type="button"
              onClick={handleApply}
              className="w-full py-2.5 px-4 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white font-bold text-xs rounded-xl shadow-sm hover:shadow transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>🤖</span>
              <span>
                {isHi
                  ? "इन मानों से AI एजेंट चलाएँ (ReAct Trace)"
                  : "Run ReAct Agent with These Parameters"}
              </span>
            </button>
            <p className="text-[10px] text-center text-slate-500 mt-1.5">
              {isHi
                ? "नियम ट्री (AST) व राजपत्रित परिपत्रों (RAG) से सत्यापन होगा"
                : "Executes multi-step reasoning with official gazetted citations"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EligibilitySimulator;
