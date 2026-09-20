"use client";

import React, { useState, useEffect, useRef } from "react";

interface QuickNeedOption {
  id: string;
  icon: string;
  label_hi: string;
  label_en: string;
  query_hi: string;
  query_en: string;
}

const QUICK_NEED_OPTIONS: QuickNeedOption[] = [
  {
    id: "agriculture",
    icon: "🌾",
    label_hi: "खेती व फसल",
    label_en: "Agriculture",
    query_hi: "मुझे खेती और फसल के लिए आर्थिक सहायता चाहिए",
    query_en: "I need financial assistance for agriculture and farming",
  },
  {
    id: "pension",
    icon: "👴",
    label_hi: "वृद्धावस्था पेंशन",
    label_en: "Pension",
    query_hi: "मुझे वृद्धावस्था अथवा सामाजिक सुरक्षा पेंशन चाहिए",
    query_en: "I am looking for old age or social security pension",
  },
  {
    id: "scholarship",
    icon: "🎓",
    label_hi: "छात्रवृत्ति व पढ़ाई",
    label_en: "Scholarship",
    query_hi: "मुझे पढ़ाई के लिए छात्रवृत्ति या शिक्षा सहायता चाहिए",
    query_en: "I need scholarship and education assistance for studies",
  },
  {
    id: "health",
    icon: "🏥",
    label_hi: "इलाज व स्वास्थ्य",
    label_en: "Health",
    query_hi: "मुझे स्वास्थ्य बीमा अथवा इलाज के लिए सहायता चाहिए",
    query_en: "I need health insurance and medical treatment support",
  },
  {
    id: "women",
    icon: "👩",
    label_hi: "महिला सहायता",
    label_en: "Women Support",
    query_hi: "मुझे महिला कल्याण एवं सहायता योजना चाहिए",
    query_en: "I need women welfare and maternity assistance schemes",
  },
  {
    id: "employment",
    icon: "💼",
    label_hi: "स्वरोजगार व लोन",
    label_en: "Employment",
    query_hi: "मुझे स्वरोजगार या रोजगार के लिए सहायता चाहिए",
    query_en: "I need self-employment loan or job assistance",
  },
];

interface NeedInputProps {
  lang?: "hi" | "en";
  language?: "hi" | "en";
  onSubmit?: (needText: string) => void;
  onSubmitNeed?: (needText: string) => void;
  isLoading: boolean;
}

export function NeedInput({
  lang: propLang,
  language,
  onSubmit,
  onSubmitNeed,
  isLoading,
}: NeedInputProps) {
  const activeLang = language || propLang || "hi";
  const handleSubmitNeed = onSubmit || onSubmitNeed || (() => {});
  const [needText, setNeedText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef<any>(null);

  const isHi = activeLang === "hi";

  // Check Web Speech API availability on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        try {
          const rec = new SpeechRecognition();
          rec.continuous = false;
          rec.interimResults = true;
          rec.lang = isHi ? "hi-IN" : "en-IN";

          rec.onresult = (event: any) => {
            const transcript = Array.from(event.results)
              .map((res: any) => res[0].transcript)
              .join("");
            setNeedText(transcript);
          };

          rec.onerror = (event: any) => {
            console.warn("Speech recognition error:", event.error);
            setIsListening(false);
          };

          rec.onend = () => {
            setIsListening(false);
          };

          recognitionRef.current = rec;
        } catch {
          setSpeechSupported(false);
        }
      } else {
        setSpeechSupported(false);
      }
    }
  }, [isHi]);

  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.lang = isHi ? "hi-IN" : "en-IN";
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.warn("Could not start speech recognition:", err);
        setIsListening(false);
      }
    } else {
      // Fallback: simulate vernacular speech recognition turn for testing
      const sampleQueries = isHi
        ? [
            "मुझे खेती और फसल के लिए आर्थिक सहायता चाहिए",
            "मेरी आयु 62 वर्ष है और मुझे वृद्धावस्था पेंशन चाहिए",
            "मुझे बच्चों की पढ़ाई के लिए सरकारी छात्रवृत्ति चाहिए",
          ]
        : [
            "I need financial assistance for agriculture and farming",
            "I am looking for elderly pension scheme for senior citizens",
            "I need medical insurance and health treatment support",
          ];
      const randomQuery =
        sampleQueries[Math.floor(Math.random() * sampleQueries.length)];
      setNeedText(randomQuery);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!needText.trim() || isLoading) return;
    handleSubmitNeed(needText.trim());
  };

  const handleQuickSelect = (option: QuickNeedOption) => {
    if (isLoading) return;
    const selectedText = isHi ? option.query_hi : option.query_en;
    setNeedText(selectedText);
    handleSubmitNeed(selectedText);
  };

  return (
    <div className="bg-white rounded-3xl p-6 sm:p-10 shadow-sm border border-slate-200 text-center space-y-6 max-w-3xl mx-auto">
      {/* Friendly Conversational Heading */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-orange-50 text-orange-700 border border-orange-200">
          <span>✨</span>
          <span>
            {isHi
              ? "सरल आवाज व टेक्स्ट खोज"
              : "Vernacular Voice & Text Discovery"}
          </span>
        </div>

        <h1 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
          {isHi
            ? "राजस्थान की सरकारी योजनाएँ खोजें"
            : "Discover Rajasthan Welfare Schemes"}
        </h1>
        <p className="text-sm sm:text-base text-slate-600 font-medium max-w-xl mx-auto">
          {isHi
            ? "बोलकर या लिखकर बताएं कि आपको किस तरह की मदद चाहिए (जैसे: खेती, पेंशन, छात्रवृत्ति, इलाज)"
            : "Describe your requirement or click the microphone to speak in Hindi or English"}
        </p>
      </div>

      {/* Free Text & Voice Input Form */}
      <form onSubmit={handleSubmit} className="space-y-4 max-w-2xl mx-auto">
        <div className="relative group">
          <textarea
            id="input-need-text"
            rows={3}
            value={needText}
            onChange={(e) => setNeedText(e.target.value)}
            disabled={isLoading}
            placeholder={
              isHi
                ? "अपनी आवश्यकता यहाँ लिखें या माइक पर क्लिक करके बोलें (उदा: मुझे खेती के लिए आर्थिक मदद चाहिए)…"
                : "Type your requirement here or click the microphone to speak (e.g. I need financial support for agriculture)…"
            }
            className={`w-full px-4 py-3.5 pr-14 text-base text-slate-900 bg-slate-50 border rounded-2xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-all resize-none shadow-inner placeholder:text-slate-400 disabled:opacity-60 ${
              isListening
                ? "border-orange-500 ring-2 ring-orange-400 bg-orange-50/20"
                : "border-slate-300"
            }`}
          />

          {/* Voice Microphone Button */}
          <button
            type="button"
            id="btn-voice-input"
            onClick={toggleListening}
            disabled={isLoading}
            title={
              isListening
                ? isHi
                  ? "सुनना बंद करें"
                  : "Stop listening"
                : isHi
                ? "बोलकर बताएं (माइक)"
                : "Speak your requirement"
            }
            className={`absolute right-3.5 top-3.5 w-10 h-10 rounded-xl flex items-center justify-center transition-all shadow-xs ${
              isListening
                ? "bg-rose-600 text-white animate-pulse-mic"
                : "bg-orange-100 text-orange-700 hover:bg-orange-200 active:scale-95"
            }`}
          >
            {isListening ? (
              <span className="text-base font-black">⏹</span>
            ) : (
              <span className="text-xl">🎙️</span>
            )}
          </button>
        </div>

        {/* Listening Active Feedback */}
        {isListening && (
          <div className="flex items-center justify-center gap-2 text-xs font-bold text-orange-600 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-rose-600 animate-ping" />
            <span>
              {isHi
                ? "सुन रहे हैं... बोलिए (उदा: 'मुझे बुजुर्ग पेंशन चाहिए')"
                : "Listening... speak now (e.g. 'I need old age pension')"}
            </span>
          </div>
        )}

        {/* Submit Action */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            type="submit"
            id="btn-submit-need"
            disabled={!needText.trim() || isLoading}
            className="w-full sm:w-auto px-8 py-3.5 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white font-extrabold text-base rounded-2xl shadow-lg shadow-orange-600/20 hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
          >
            {isLoading ? (
              <>
                <svg
                  className="animate-spin h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                <span>
                  {isHi ? "योजनाएँ जाँची जा रही हैं…" : "Checking schemes…"}
                </span>
              </>
            ) : (
              <>
                <span>{isHi ? "योजनाएँ खोजें" : "Discover Schemes"}</span>
                <span className="text-lg">→</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Quick Need Shortcut Chips */}
      <div className="pt-4 border-t border-slate-100 space-y-3">
        <p className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
          {isHi ? "या तुरंत विषय चुनें" : "Or select a popular category"}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2.5 max-w-2xl mx-auto">
          {QUICK_NEED_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              id={`quick-chip-${opt.id}`}
              onClick={() => handleQuickSelect(opt)}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs sm:text-sm font-bold bg-slate-100 hover:bg-orange-50 hover:text-orange-700 hover:border-orange-300 text-slate-700 border border-slate-200 transition-all active:scale-95 disabled:opacity-50 cursor-pointer shadow-xs"
            >
              <span className="text-base">{opt.icon}</span>
              <span>{isHi ? opt.label_hi : opt.label_en}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default NeedInput;
