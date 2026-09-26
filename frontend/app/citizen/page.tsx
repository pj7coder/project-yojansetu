"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  CitizenChatSidebar,
  ChatSessionMeta,
} from "../../components/citizen/CitizenChatSidebar";
import {
  CitizenParameterPanel,
  CitizenParameters,
  DEFAULT_CITIZEN_PARAMETERS,
} from "../../components/citizen/CitizenParameterPanel";
import { sendAgentQuery, getCitizenSchemeDetail } from "../../lib/api";
import { CitizenSchemeDetail } from "../../types/citizen";
import {
  AgentQueryResponse,
  RecommendedScheme,
  SchemeCitation,
  RequiredDocument,
  EmitraKioskInfo,
} from "../../types/agent";
import { LanguageToggle } from "../../components/citizen/LanguageToggle";
import CitationDrawer from "../../components/citizen/CitationDrawer";
import EmitraSlipModal from "../../components/citizen/EmitraSlipModal";
import SchemeDetails from "../../components/citizen/SchemeDetails";
import { RAJASTHAN_FLAGSHIP_SCHEMES } from "../../lib/rajasthanSchemesData";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  schemes?: RecommendedScheme[];
  documents?: RequiredDocument[];
  citations?: SchemeCitation[];
  kioskInfo?: EmitraKioskInfo;
  reasoningSteps?: any[];
}

const STORAGE_CHATS_KEY = "yojansetu_citizen_chat_sessions_v2";
const STORAGE_CURRENT_CHAT_ID = "yojansetu_active_chat_id_v2";

export default function CitizenPage() {
  const [lang, setLang] = useState<"hi" | "en">("hi");
  const [inputText, setInputText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [parameters, setParameters] = useState<CitizenParameters>(
    DEFAULT_CITIZEN_PARAMETERS
  );

  // Layout Drawers (Sidebar & Right Panel)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isParamsOpen, setIsParamsOpen] = useState(true);

  // Past Chats
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Speech Recognition (Voice)
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);

  // Modals & Drawers
  const [selectedCitation, setSelectedCitation] = useState<SchemeCitation | null>(
    null
  );
  const [isEmitraSlipOpen, setIsEmitraSlipOpen] = useState(false);
  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [schemeDetail, setSchemeDetail] = useState<CitizenSchemeDetail | null>(null);

  const handleOpenSchemeDetail = async (schemeCode: string) => {
    setSelectedSchemeId(schemeCode);
    try {
      const detail = await getCitizenSchemeDetail(schemeCode, lang);
      setSchemeDetail(detail);
    } catch {
      const fallbackItem = RAJASTHAN_FLAGSHIP_SCHEMES.find(
        (s) => s.code === schemeCode || s.code.includes(schemeCode)
      );
      if (fallbackItem) {
        setSchemeDetail({
          scheme_id: fallbackItem.code,
          scheme_code: fallbackItem.code,
          name_hi: fallbackItem.name_hi,
          name_en: fallbackItem.name_en,
          version_number: 1,
          status: "VERIFIED",
          is_active: true,
          department_hi: fallbackItem.department_hi,
          department_en: fallbackItem.department_en,
          category_hi: fallbackItem.category,
          category_en: fallbackItem.category,
          purpose_hi: fallbackItem.desc_hi,
          purpose_en: fallbackItem.desc_en,
          why_eligible_hi: ["आपकी वर्तमान प्रोफाइल इस योजना के मुख्य मानदंडों को पूरा करती है।"],
          why_eligible_en: ["Your current profile meets the primary criteria for this scheme."],
          eligibility_conditions_hi: ["राजस्थान राज्य का मूल निवासी", "आय एवं पात्रता सीमा के अंतर्गत"],
          eligibility_conditions_en: ["Resident of Rajasthan state", "Within prescribed income rules"],
          benefits: [
            {
              benefit_type: "DIRECT_BENEFIT",
              currency: "INR",
              display_text_hi: fallbackItem.payout_summary_hi,
              display_text_en: fallbackItem.payout_summary_en,
            },
          ],
          required_documents: fallbackItem.mandatory_docs.map((d) => ({
            document_name_en: d.name_en,
            document_name_hi: d.name_hi,
            is_mandatory: true,
          })),
          application: {
            channels: ["E_MITRA", "ONLINE_PORTAL"],
            portal_url: "https://emitra.rajasthan.gov.in",
            is_portal_url_safe: true,
            guidance_note_hi: fallbackItem.apply_channel_hi,
            guidance_note_en: fallbackItem.apply_channel_en,
            steps_hi: ["निकटतम ई-मित्र केंद्र पर जाएं", "आवश्यक दस्तावेज़ प्रस्तुत करें", "आवेदन रसीद प्राप्त करें"],
            steps_en: ["Visit nearest e-Mitra kiosk", "Present mandatory documents", "Obtain application slip"],
          },
          important_dates: [],
          official_source: {
            department_hi: fallbackItem.department_hi,
            department_en: fallbackItem.department_en,
            notification_reference: fallbackItem.circular_no,
          },
        });
      }
    }
  };

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const isHi = lang === "hi";

  // Auto-scroll chat to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isProcessing]);

  // Load Past Chats from localStorage on Mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_CHATS_KEY);
      if (stored) {
        const parsed: { sessions: ChatSessionMeta[]; sessionData: Record<string, { messages: ChatMessage[]; parameters: CitizenParameters }> } = JSON.parse(stored);
        if (parsed.sessions && parsed.sessions.length > 0) {
          setSessions(parsed.sessions);
          const activeId = localStorage.getItem(STORAGE_CURRENT_CHAT_ID) || parsed.sessions[0].id;
          setActiveSessionId(activeId);
          if (parsed.sessionData && parsed.sessionData[activeId]) {
            setMessages(parsed.sessionData[activeId].messages || []);
            if (parsed.sessionData[activeId].parameters) {
              setParameters(parsed.sessionData[activeId].parameters);
            }
          }
          return;
        }
      }
    } catch (e) {
      console.error("Failed to load past chats:", e);
    }

    // Default: initialize first session
    startNewChat();
  }, []);

  // Save current conversation to localStorage
  const persistSession = (
    sessionId: string,
    msgs: ChatMessage[],
    params: CitizenParameters,
    firstUserPrompt?: string
  ) => {
    try {
      const stored = localStorage.getItem(STORAGE_CHATS_KEY);
      let data: {
        sessions: ChatSessionMeta[];
        sessionData: Record<string, { messages: ChatMessage[]; parameters: CitizenParameters }>;
      } = stored ? JSON.parse(stored) : { sessions: [], sessionData: {} };

      let existingMeta = data.sessions.find((s) => s.id === sessionId);
      const title =
        firstUserPrompt ||
        (existingMeta ? existingMeta.title : isHi ? "नई बातचीत" : "New Conversation");

      const meta: ChatSessionMeta = {
        id: sessionId,
        title: title.length > 28 ? title.slice(0, 28) + "..." : title,
        timestamp: Date.now(),
        messageCount: msgs.length,
        lastMessage: msgs.length > 0 ? msgs[msgs.length - 1].text.slice(0, 45) : "",
      };

      const updatedSessions = [meta, ...data.sessions.filter((s) => s.id !== sessionId)];
      data.sessions = updatedSessions;
      data.sessionData[sessionId] = {
        messages: msgs,
        parameters: params,
      };

      localStorage.setItem(STORAGE_CHATS_KEY, JSON.stringify(data));
      localStorage.setItem(STORAGE_CURRENT_CHAT_ID, sessionId);
      setSessions(updatedSessions);
    } catch (e) {
      console.error("Failed to persist chat:", e);
    }
  };

  // Start a fresh conversation
  const startNewChat = () => {
    const newId = `chat_${Date.now()}`;
    const initialGreeting: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: "assistant",
      text: isHi
        ? "नमस्ते! मैं आपका योजनसेतु AI सहायक हूँ। राजस्थान सरकार की पेंशन, कृषि, स्वास्थ्य, छात्रवृत्ति व स्वरोजगार योजनाओं की सटीक जानकारी के लिए पूछें।"
        : "Hello! I am your YojanSetu AI Assistant. Ask any question regarding Rajasthan welfare schemes, pensions, farmer subsidies, or healthcare benefits.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setActiveSessionId(newId);
    setMessages([initialGreeting]);
    persistSession(newId, [initialGreeting], parameters);
  };

  // Switch to a past chat session
  const handleSelectSession = (sessionId: string) => {
    try {
      const stored = localStorage.getItem(STORAGE_CHATS_KEY);
      if (stored) {
        const data = JSON.parse(stored);
        if (data.sessionData && data.sessionData[sessionId]) {
          setActiveSessionId(sessionId);
          setMessages(data.sessionData[sessionId].messages || []);
          if (data.sessionData[sessionId].parameters) {
            setParameters(data.sessionData[sessionId].parameters);
          }
          localStorage.setItem(STORAGE_CURRENT_CHAT_ID, sessionId);
        }
      }
    } catch (e) {
      console.error("Error switching session:", e);
    }
  };

  // Delete a chat session
  const handleDeleteSession = (sessionId: string) => {
    try {
      const stored = localStorage.getItem(STORAGE_CHATS_KEY);
      if (stored) {
        const data = JSON.parse(stored);
        data.sessions = data.sessions.filter((s: ChatSessionMeta) => s.id !== sessionId);
        delete data.sessionData[sessionId];
        localStorage.setItem(STORAGE_CHATS_KEY, JSON.stringify(data));
        setSessions(data.sessions);

        if (activeSessionId === sessionId) {
          if (data.sessions.length > 0) {
            handleSelectSession(data.sessions[0].id);
          } else {
            startNewChat();
          }
        }
      }
    } catch (e) {
      console.error("Error deleting session:", e);
    }
  };

  // Convert current parameters into context object
  const getContextFromParameters = (params: CitizenParameters) => ({
    age: params.age,
    gender: params.gender,
    social_category: params.category,
    annual_income: params.income,
    occupation: params.occupation,
    residence: params.residence,
    district: params.district,
    ration_card: params.rationCard,
    is_widow: params.isWidow,
    is_disabled: params.isDisabled,
    disability_percent: params.disabilityPercent,
    land_area_bigha: params.landBigha,
    has_jan_aadhaar: params.hasJanAadhaar,
    is_student: params.isStudent,
    marital_status: params.maritalStatus,
  });

  // Calculate live matching schemes from catalog
  const matchingFlagshipCount = React.useMemo(() => {
    const profile = getContextFromParameters(parameters);
    return RAJASTHAN_FLAGSHIP_SCHEMES.filter((s) => s.isEligible(profile)).length;
  }, [parameters]);

  // Send Chat Query
  const handleSendMessage = async (customQuery?: string) => {
    const query = (customQuery || inputText).trim();
    if (!query || isProcessing) return;

    setInputText("");
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setIsProcessing(true);

    const isFirstQuery = messages.length <= 1;
    const currentSession = activeSessionId || `chat_${Date.now()}`;
    if (!activeSessionId) setActiveSessionId(currentSession);

    try {
      const context = getContextFromParameters(parameters);
      const resp: AgentQueryResponse = await sendAgentQuery(
        query,
        context,
        lang === "hi" ? "hi" : "en"
      );

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: "assistant",
        text: resp.final_answer || (isHi ? "यहाँ आपकी पात्रता और योजनाओं की जानकारी है।" : "Here is your eligibility and scheme information."),
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        schemes: resp.structured_data?.recommended_schemes || [],
        documents: resp.structured_data?.required_documents || [],
        citations: resp.structured_data?.citations || [],
        kioskInfo: resp.structured_data?.emitra_kiosk_info,
        reasoningSteps: resp.steps || [],
      };

      const finalMessages = [...updatedMessages, assistantMsg];
      setMessages(finalMessages);
      persistSession(
        currentSession,
        finalMessages,
        parameters,
        isFirstQuery ? query : undefined
      );
    } catch (err: any) {
      console.error("Chat agent error:", err);
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: "assistant",
        text: isHi
          ? "क्षमा करें, उत्तर प्राप्त करने में समस्या आई। कृपया पुनः प्रयास करें।"
          : "Sorry, could not process request right now. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages([...updatedMessages, errorMsg]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Right Panel "Apply to Chat"
  const handleApplyParametersToChat = (newParams: CitizenParameters) => {
    setParameters(newParams);
    const query = isHi
      ? `मेरी प्रोफाइल: उम्र ${newParams.age} वर्ष, ${newParams.gender === "FEMALE" ? "महिला" : "पुरुष"}, ${newParams.category} श्रेणी, वार्षिक आय ₹${newParams.income.toLocaleString("en-IN")}, व्यवसाय ${newParams.occupation}, जिला ${newParams.district}, भूमि ${newParams.landBigha} बीघा। मुझे किन सरकारी योजनाओं का लाभ मिलेगा?`
      : `My profile: Age ${newParams.age}, ${newParams.gender.toLowerCase()}, ${newParams.category}, Annual income ₹${newParams.income.toLocaleString("en-IN")}, Occupation ${newParams.occupation}, District ${newParams.district}, Land ${newParams.landBigha} bigha. What schemes and pensions am I eligible for?`;

    handleSendMessage(query);
  };

  // Working Voice Recognition
  const toggleVoice = () => {
    if (isListening) {
      // Stop listening
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
      setIsListening(false);
      return;
    }

    setSpeechError(null);
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      // Web Speech not available in this browser; provide helpful prompt
      setSpeechError(
        isHi
          ? "इस ब्राउज़र में स्पीच रिकग्निशन उपलब्ध नहीं है। कृपया लिखकर पूछें।"
          : "Speech recognition not supported in this browser. Please type."
      );
      setTimeout(() => setSpeechError(null), 4000);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = lang === "hi" ? "hi-IN" : "en-IN";
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setInputText(transcript);
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech error:", event.error);
        setIsListening(false);
        if (event.error === "not-allowed") {
          setSpeechError(isHi ? "माइक्रोफ़ोन अनुमति अस्वीकृत है।" : "Microphone permission denied.");
        } else {
          setSpeechError(isHi ? "आवाज नहीं पहचानी जा सकी।" : "Could not hear audio clearly.");
        }
        setTimeout(() => setSpeechError(null), 3000);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch (err: any) {
      console.error("Speech initialization error:", err);
      setIsListening(false);
      setSpeechError(isHi ? "माइक्रोफ़ोन प्रारंभ नहीं हो सका।" : "Could not start microphone.");
      setTimeout(() => setSpeechError(null), 3000);
    }
  };

  return (
    <div className="h-screen w-full flex flex-col bg-slate-100 overflow-hidden font-sans">
      {/* Top Navbar */}
      <header className="h-14 bg-white border-b border-slate-200 px-3 sm:px-4 flex items-center justify-between flex-shrink-0 z-30 shadow-2xs">
        <div className="flex items-center gap-2.5">
          {/* Toggle Sidebar Button */}
          <button
            type="button"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-700 transition"
            title={isSidebarOpen ? "Hide chat history" : "Show chat history"}
          >
            <span className="text-sm">📋</span>
          </button>

          {/* Logo */}
          <Link href="/citizen" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-orange-600 flex items-center justify-center text-white font-black text-sm shadow-xs">
              YS
            </div>
            <div>
              <div className="font-black text-sm tracking-tight text-slate-900 leading-none">
                योजनसेतु AI
              </div>
              <div className="text-[10px] text-orange-700 font-semibold leading-none mt-0.5">
                {isHi ? "नागरिक कल्याण सहायक" : "Vernacular Scheme Assistant"}
              </div>
            </div>
          </Link>
        </div>

        {/* Center Status / Matching schemes badge */}
        <div className="hidden md:flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>{isHi ? "सक्रिय सहायक" : "AI Assistant Ready"}</span>
          </span>
          <span className="text-xs text-slate-500 font-medium">
            • {matchingFlagshipCount} {isHi ? "संभावित योजनाएं उपलब्ध" : "potential schemes match"}
          </span>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-2">
          <LanguageToggle currentLang={lang} onLanguageChange={(l) => setLang(l)} />

          <button
            type="button"
            onClick={() => setIsParamsOpen(!isParamsOpen)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-bold transition ${
              isParamsOpen
                ? "bg-orange-50 border-orange-300 text-orange-700"
                : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
            }`}
            title="Toggle Parameter Panel"
          >
            <span>⚙️</span>
            <span className="hidden sm:inline">
              {isHi ? "प्रोफाइल पैरामीटर" : "Parameters"}
            </span>
          </button>
        </div>
      </header>

      {/* Main 3-Panel Layout Container */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        {/* 1. Left Banner: Past Chats History */}
        <CitizenChatSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewChat={startNewChat}
          onDeleteSession={handleDeleteSession}
          lang={lang}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />

        {/* 2. Center Area: Smart Chatbot Window */}
        <main className="flex-1 flex flex-col bg-white min-w-0 h-full relative">
          {/* Chat Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 scrollbar-thin">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex items-start gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}
                >
                  {!isUser && (
                    <div className="w-8 h-8 rounded-full bg-orange-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-xs mt-0.5">
                      YS
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] sm:max-w-[78%] rounded-2xl p-3.5 sm:p-4 text-xs sm:text-sm leading-relaxed ${
                      isUser
                        ? "bg-gradient-to-r from-orange-600 to-amber-600 text-white shadow-sm rounded-tr-xs"
                        : "bg-slate-50 text-slate-800 border border-slate-200 shadow-2xs rounded-tl-xs"
                    }`}
                  >
                    {/* Message Text */}
                    <div className="whitespace-pre-wrap font-medium">{msg.text}</div>

                    {/* Eligible Scheme Cards */}
                    {msg.schemes && msg.schemes.length > 0 && (
                      <div className="mt-3.5 space-y-2.5 pt-3 border-t border-slate-200">
                        <div className="text-[11px] font-black uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                          <span>🎯</span>
                          <span>
                            {isHi ? "पात्र कल्याणकारी योजनाएं" : "Eligible Welfare Schemes"} (
                            {msg.schemes.length})
                          </span>
                        </div>

                        <div className="grid grid-cols-1 gap-2">
                          {msg.schemes.map((scheme, idx) => (
                            <div
                              key={idx}
                              className="p-3 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-orange-300 transition"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <h4 className="font-extrabold text-slate-900 text-xs sm:text-sm">
                                    {isHi ? scheme.name_hi : scheme.name_en}
                                  </h4>
                                  <span className="inline-block mt-0.5 px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold text-[10px] border border-emerald-200">
                                    ✓ {scheme.eligibility_status || (isHi ? "पूर्णतः पात्र" : "Eligible")}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleOpenSchemeDetail(scheme.scheme_code)}
                                  className="text-[11px] font-bold text-orange-600 hover:text-orange-700 bg-orange-50 px-2 py-1 rounded border border-orange-200 hover:bg-orange-100 transition whitespace-nowrap cursor-pointer"
                                >
                                  {isHi ? "विवरण देखें →" : "Details →"}
                                </button>
                              </div>

                              {scheme.benefit_summary && (
                                <p className="text-[11px] text-slate-600 mt-1 font-medium">
                                  💵 {typeof scheme.benefit_summary === "string" ? scheme.benefit_summary : JSON.stringify(scheme.benefit_summary)}
                                </p>
                              )}

                              {scheme.documents_required && scheme.documents_required.length > 0 && (
                                <div className="mt-2 text-[10px] text-slate-500">
                                  <span className="font-bold text-slate-700">
                                    {isHi ? "आवश्यक दस्तावेज़:" : "Required Docs:"}
                                  </span>{" "}
                                  {scheme.documents_required.join(", ")}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* e-Mitra Kiosk / Apply Slip CTA */}
                    {msg.kioskInfo && (
                      <div className="mt-2.5 pt-2 border-t border-slate-200 flex items-center justify-between text-[11px]">
                        <span className="text-slate-600 flex items-center gap-1 font-medium">
                          <span>🏪</span>
                          <span>
                            {isHi ? "निकटतम ई-मित्र केंद्र जानकारी उपलब्ध" : "Nearby E-Mitra Kiosk details"}
                          </span>
                        </span>
                        <button
                          type="button"
                          onClick={() => setIsEmitraSlipOpen(true)}
                          className="px-2.5 py-1 rounded bg-slate-900 text-white font-bold text-[10px] hover:bg-slate-800 transition cursor-pointer"
                        >
                          📄 {isHi ? "आवेदन पर्ची देखें" : "View Slip"}
                        </button>
                      </div>
                    )}

                    {/* Timestamp */}
                    <div
                      className={`text-[9px] mt-1.5 text-right font-mono ${
                        isUser ? "text-orange-100" : "text-slate-400"
                      }`}
                    >
                      {msg.timestamp}
                    </div>
                  </div>

                  {isUser && (
                    <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-xs mt-0.5">
                      👤
                    </div>
                  )}
                </div>
              );
            })}

            {/* Processing / Typing Indicator */}
            {isProcessing && (
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-orange-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 animate-pulse">
                  YS
                </div>
                <div className="p-3 rounded-2xl bg-slate-100 text-slate-600 text-xs font-medium flex items-center gap-2">
                  <span className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-600 animate-bounce" />
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-600 animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-600 animate-bounce [animation-delay:0.4s]" />
                  </span>
                  <span>{isHi ? "योजनाओं की पात्रता जाँची जा रही है..." : "Evaluating scheme eligibility..."}</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Quick Prompt Chips */}
          {messages.length <= 2 && (
            <div className="px-4 py-2 bg-slate-50/80 border-t border-slate-100 flex flex-wrap gap-1.5">
              {[
                { hi: "🌾 किसान सम्मान निधि व कृषि लोन", en: "Farmer subsidies & loans" },
                { hi: "👵 60+ वर्ष वृद्धावस्था पेंशन नियम", en: "Old age pension criteria" },
                { hi: "🎓 छात्रवृत्ति व अनुप्रति कोचिंग", en: "Scholarship & coaching" },
                { hi: "👩 महिला स्वरोजगार सहायता", en: "Women self-employment" },
              ].map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendMessage(isHi ? chip.hi : chip.en)}
                  className="px-2.5 py-1 rounded-full bg-white hover:bg-orange-50 hover:text-orange-700 hover:border-orange-300 text-slate-700 text-[11px] font-semibold border border-slate-200 transition shadow-2xs active:scale-95 cursor-pointer"
                >
                  {isHi ? chip.hi : chip.en}
                </button>
              ))}
            </div>
          )}

          {/* Speech Error Banner if any */}
          {speechError && (
            <div className="px-4 py-1.5 bg-rose-50 border-t border-rose-200 text-rose-700 text-xs flex items-center justify-between">
              <span>⚠️ {speechError}</span>
              <button
                type="button"
                onClick={() => setSpeechError(null)}
                className="text-rose-500 hover:text-rose-800 font-bold"
              >
                ✕
              </button>
            </div>
          )}

          {/* Bottom Chat Bar with Working Voice Icon */}
          <div className="p-3 sm:p-4 bg-white border-t border-slate-200 flex-shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2 bg-slate-50 border border-slate-300 rounded-2xl p-1.5 sm:p-2 focus-within:border-orange-500 focus-within:ring-2 focus-within:ring-orange-500/20 transition shadow-sm"
            >
              {/* Voice Icon with Interactive Listening State */}
              <button
                type="button"
                id="voice-mic-btn"
                onClick={toggleVoice}
                title={
                  isListening
                    ? isHi
                      ? "सुनना बंद करें"
                      : "Stop Listening"
                    : isHi
                    ? "बोलकर पूछें (आवाज सहायक)"
                    : "Speak your query (Voice Input)"
                }
                className={`relative w-10 h-10 rounded-xl flex items-center justify-center transition-all cursor-pointer flex-shrink-0 ${
                  isListening
                    ? "bg-rose-600 text-white shadow-md animate-pulse ring-4 ring-rose-500/30"
                    : "bg-orange-100 hover:bg-orange-200 text-orange-700"
                }`}
              >
                {isListening ? (
                  <span className="text-lg">⏹️</span>
                ) : (
                  <span className="text-lg">🎙️</span>
                )}
                {isListening && (
                  <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-rose-500 animate-ping" />
                )}
              </button>

              {/* Text Input */}
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={
                  isListening
                    ? isHi
                      ? "सुन रहा हूँ... बोलिए..."
                      : "Listening... please speak..."
                    : isHi
                    ? "योजना के बारे में पूछें या अपनी समस्या बताएं..."
                    : "Ask about welfare schemes or state your need..."
                }
                className="flex-1 bg-transparent border-none text-slate-800 placeholder-slate-400 text-xs sm:text-sm font-medium focus:outline-none px-2"
              />

              {/* Send Button */}
              <button
                type="submit"
                disabled={!inputText.trim() || isProcessing}
                className="w-10 h-10 rounded-xl bg-orange-600 hover:bg-orange-500 active:scale-95 disabled:opacity-40 text-white flex items-center justify-center shadow-sm transition-all cursor-pointer flex-shrink-0"
                title={isHi ? "भेजें" : "Send query"}
              >
                <span className="text-base">🚀</span>
              </button>
            </form>
          </div>
        </main>

        {/* 3. Right Parameter Panel: Citizen Details Customization */}
        <CitizenParameterPanel
          parameters={parameters}
          onChange={(newParams) => setParameters(newParams)}
          onApplyToChat={handleApplyParametersToChat}
          lang={lang}
          isOpen={isParamsOpen}
          onClose={() => setIsParamsOpen(false)}
        />
      </div>

      {/* Citations Drawer Modal */}
      {selectedCitation && (
        <CitationDrawer
          citation={selectedCitation}
          language={lang}
          onClose={() => setSelectedCitation(null)}
        />
      )}

      {/* Emitra Slip Modal */}
      {isEmitraSlipOpen && (
        <EmitraSlipModal
          isOpen={isEmitraSlipOpen}
          onClose={() => setIsEmitraSlipOpen(false)}
          language={lang}
          citizenName={parameters.gender === "FEMALE" ? "नागरिक (महिला)" : "नागरिक"}
          district={parameters.district}
          age={parameters.age}
          gender={parameters.gender}
          schemes={messages.flatMap((m) => m.schemes || [])}
          documents={messages.flatMap((m) => m.documents || [])}
          kioskInfo={messages.find((m) => m.kioskInfo)?.kioskInfo || null}
        />
      )}

      {/* Scheme Details Modal */}
      {selectedSchemeId && schemeDetail && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl relative">
            <SchemeDetails
              scheme={schemeDetail}
              lang={lang}
              onBack={() => {
                setSelectedSchemeId(null);
                setSchemeDetail(null);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
