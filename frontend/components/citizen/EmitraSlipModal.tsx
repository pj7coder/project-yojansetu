"use client";

import React from "react";
import { RecommendedScheme, RequiredDocument, EmitraKioskInfo } from "@/types/agent";

interface EmitraSlipModalProps {
  language: "hi" | "en";
  isOpen: boolean;
  onClose: () => void;
  citizenName?: string;
  district?: string;
  age?: number;
  gender?: string;
  schemes: RecommendedScheme[];
  documents: RequiredDocument[];
  kioskInfo?: EmitraKioskInfo | null;
}

export function EmitraSlipModal({
  language,
  isOpen,
  onClose,
  citizenName = "नागरिक (Citizen)",
  district = "Rajasthan",
  age,
  gender,
  schemes,
  documents,
  kioskInfo,
}: EmitraSlipModalProps) {
  const isHi = language === "hi";

  if (!isOpen) return null;

  const handlePrint = () => {
    window.print();
  };

  const slipNumber = `RJ-EMITRA-2026-${Math.floor(100000 + Math.random() * 900000)}`;
  const currentDate = new Date().toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-300 max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Top Controls Bar (Hidden during print) */}
        <div className="bg-slate-900 text-white px-4 py-2.5 flex items-center justify-between print:hidden">
          <div className="flex items-center gap-2 text-xs font-bold">
            <span>🖨️</span>
            <span>
              {isHi ? "ई-मित्र आवेदन टोकन रसीद" : "e-Mitra Kiosk Application Slip"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="px-3 py-1 bg-orange-600 hover:bg-orange-700 text-white font-bold text-xs rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <span>🖨️</span>
              <span>{isHi ? "प्रिंट / PDF सेव करें" : "Print / Save PDF"}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center text-xs font-bold transition-colors cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Printable Slip Content */}
        <div className="p-6 overflow-y-auto space-y-5 text-slate-900 print:p-8" id="emitra-slip-area">
          {/* Slip Header */}
          <div className="border-b-2 border-slate-900 pb-4 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-orange-600 text-white font-black text-2xl mb-2">
              YS
            </div>
            <div className="text-sm font-black tracking-wider uppercase text-slate-800">
              Government of Rajasthan • राजस्थान सरकार
            </div>
            <h2 className="text-lg font-black text-slate-900 tracking-tight">
              ई-मित्र नागरिक योजना परामर्श एवं आवेदन पर्ची
            </h2>
            <div className="text-xs text-slate-600 font-semibold mt-0.5">
              e-Mitra Citizen Scheme Guidance & Kiosk Submission Slip
            </div>

            <div className="flex justify-between items-center text-xs font-mono font-bold mt-3 pt-2 border-t border-dashed border-slate-300">
              <span>Slip No: {slipNumber}</span>
              <span>Date: {currentDate}</span>
            </div>
          </div>

          {/* Citizen Demographics Table */}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
              {isHi ? "1. नागरिक विवरण (Citizen Profile)" : "1. Citizen Demographics"}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs">
              <div>
                <span className="text-slate-500 block text-[10px]">नाम (Name)</span>
                <span className="font-bold">{citizenName}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">जिला (District)</span>
                <span className="font-bold">{district}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">उम्र (Age)</span>
                <span className="font-bold">{age ? `${age} वर्ष` : "सत्यापित"}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">लिंग (Gender)</span>
                <span className="font-bold">{gender || "नागरिक"}</span>
              </div>
            </div>
          </div>

          {/* Matched Schemes */}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5 flex justify-between">
              <span>{isHi ? "2. पात्र सरकारी योजनाएं" : "2. Eligible Welfare Schemes"}</span>
              <span className="font-mono text-orange-700">{schemes.length} Schemes</span>
            </div>
            <div className="border border-slate-200 rounded-xl overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-slate-100 font-bold text-slate-700 border-b border-slate-200">
                  <tr>
                    <th className="p-2.5">योजना का नाम (Scheme Name)</th>
                    <th className="p-2.5">अनुमानित लाभ (Benefit)</th>
                    <th className="p-2.5 text-right">स्थिति (Status)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {schemes.map((s, idx) => {
                    const benefitText = typeof s.benefit_summary === 'object' && s.benefit_summary !== null
                      ? ((s.benefit_summary as any).monthly_payout_inr
                          ? `₹${(s.benefit_summary as any).monthly_payout_inr}/माह`
                          : (s.benefit_summary as any).slab_applied || 'डीबीटी वित्तीय सहायता')
                      : (s.benefit_summary || "डीबीटी सीधे खाते में");
                    return (
                    <tr key={idx} className="hover:bg-slate-50/60">
                      <td className="p-2.5 font-bold text-slate-800">
                        {isHi ? s.name_hi || s.name_en : s.name_en}
                        <span className="block text-[10px] font-mono text-slate-400">
                          {s.scheme_code}
                        </span>
                      </td>
                      <td className="p-2.5 font-bold text-emerald-700">
                        {benefitText}
                      </td>
                      <td className="p-2.5 text-right">
                        <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold text-[10px]">
                          पात्र (Eligible)
                        </span>
                      </td>
                    </tr>
                    );
                  })}
                  {schemes.length === 0 && (
                    <tr>
                      <td colSpan={3} className="p-4 text-center text-slate-400">
                        कोई योजना संलग्न नहीं है।
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mandatory Checklist */}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
              {isHi
                ? "3. ई-मित्र पर ले जाने हेतु आवश्यक दस्तावेज (Checklist)"
                : "3. Mandatory Documents for Kiosk Operator"}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {documents.map((doc, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                >
                  <input
                    type="checkbox"
                    defaultChecked={false}
                    className="mt-0.5 accent-orange-600 rounded"
                  />
                  <div>
                    <span className="font-bold text-slate-800">{doc.document_name}</span>
                    <span className="block text-[10px] text-slate-500">{doc.purpose}</span>
                  </div>
                </div>
              ))}
              {documents.length === 0 && (
                <div className="col-span-2 text-xs text-slate-400 italic">
                  मूल जन आधार कार्ड व बैंक पासबुक अनिवार्य है।
                </div>
              )}
            </div>
          </div>

          {/* Kiosk Guidance & Statutory Warning */}
          <div className="bg-amber-50 border border-amber-200 p-3 rounded-xl text-xs space-y-1">
            <div className="font-bold text-amber-900 flex items-center gap-1.5">
              <span>ℹ️</span>
              <span>
                {isHi
                  ? "ई-मित्र केंद्र निर्देश एवं वैधानिक शुल्क"
                  : "e-Mitra Center Statutory Charges"}
              </span>
            </div>
            <p className="text-[11px] text-amber-800">
              {kioskInfo?.citizen_tip ||
                "राजस्थान सरकार द्वारा ई-मित्र पर योजना आवेदन का अधिकतम सेवा शुल्क ₹50 निर्धारित है। ऑपरेटर से आधिकारिक डिजिटल रसीद अवश्य प्राप्त करें।"}
            </p>
            <div className="text-[10px] text-slate-500 font-mono pt-1">
              हेल्पलाइन: 181 (CM Helpline) • e-Mitra Support: 0141-2221424
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-100 border-t border-slate-200 flex justify-end gap-2 print:hidden">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
          >
            {isHi ? "बंद करें" : "Close"}
          </button>
          <button
            type="button"
            onClick={handlePrint}
            className="px-4 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors flex items-center gap-1 cursor-pointer"
          >
            <span>🖨️</span>
            <span>{isHi ? "प्रिंट पर्ची" : "Print Slip"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default EmitraSlipModal;
