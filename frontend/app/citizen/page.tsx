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
  FollowUpQuestion,
} from "../../types/agent";
import { LanguageToggle } from "../../components/citizen/LanguageToggle";
import CitationDrawer from "../../components/citizen/CitationDrawer";
import EmitraSlipModal from "../../components/citizen/EmitraSlipModal";
import SchemeDetails from "../../components/citizen/SchemeDetails";
import { RAJASTHAN_FLAGSHIP_SCHEMES } from "../../lib/rajasthanSchemesData";
import { extractDemographicsFromText } from "../../lib/extractDemographics";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  schemes?: RecommendedScheme[];
  candidateSchemes?: RecommendedScheme[];
  documents?: RequiredDocument[];
  citations?: SchemeCitation[];
  kioskInfo?: EmitraKioskInfo;
  reasoningSteps?: any[];
  confidenceScore?: number;
  confidenceLevel?: "HIGH" | "MEDIUM" | "LOW";
  followUpQuestion?: FollowUpQuestion | null;
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
  const [lastUpdatedField, setLastUpdatedField] = useState<string | null>(null);

  // Layout Drawers (Sidebar & Right Panel)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isParamsOpen, setIsParamsOpen] = useState(true);

  // Past Chats
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Speech Recognition (Voice) with Intelligent Auto-Send & Silence Detection
  const [isListening, setIsListening] = useState(false);
  const [speechStatus, setSpeechStatus] = useState<"idle" | "listening" | "hearing" | "sending">("idle");
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [voiceLang, setVoiceLang] = useState<"hi" | "en">(lang === "en" ? "en" : "hi");
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef<boolean>(false);
  const speechTextRef = useRef<string>("");
  const hasSentRef = useRef<boolean>(false);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const noSpeechTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);

  // Text-To-Speech (Assistant Voice Synthesis)
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const lastInputWasVoiceRef = useRef<boolean>(false);

  // Stop assistant speech immediately
  const stopSpeech = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
    }
    setSpeakingMsgId(null);
  }, []);

  // Speak assistant text aloud with Indian vernacular tone
  const speakText = useCallback(
    (textToSpeak: string, msgId?: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

      try {
        window.speechSynthesis.cancel();
      } catch {}

      // Clean markdown, symbols, and formatting for clean natural speech
      const clean = textToSpeak
        .replace(/[*#_~`>]/g, " ")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(/https?:\/\/\S+/g, "")
        .replace(/[^\w\s\u0900-\u097F.,?!₹%/-]/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      if (!clean) return;

      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.lang = lang === "hi" ? "hi-IN" : "en-IN";
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      try {
        const voices = window.speechSynthesis.getVoices();
        const targetPrefix = lang === "hi" ? "hi" : "en";
        const matchedVoice =
          voices.find(
            (v) =>
              v.lang.toLowerCase().startsWith(targetPrefix) &&
              (v.lang.includes("IN") || v.name.toLowerCase().includes("india"))
          ) || voices.find((v) => v.lang.toLowerCase().startsWith(targetPrefix));
        if (matchedVoice) {
          utterance.voice = matchedVoice;
        }
      } catch {}

      utterance.onstart = () => {
        setSpeakingMsgId(msgId || "active");
      };
      utterance.onend = () => {
        setSpeakingMsgId(null);
      };
      utterance.onerror = () => {
        setSpeakingMsgId(null);
      };

      window.speechSynthesis.speak(utterance);
    },
    [lang]
  );

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

  // Keep voice recognition language aligned with selected citizen language
  useEffect(() => {
    setVoiceLang(lang === "en" ? "en" : "hi");
  }, [lang]);

  const isProcessingRef = useRef(isProcessing);
  useEffect(() => {
    isProcessingRef.current = isProcessing;
  }, [isProcessing]);

  const handleSendMessageRef = useRef<((query?: string) => Promise<void>) | null>(null);
  useEffect(() => {
    handleSendMessageRef.current = handleSendMessage;
  });

  // Cleanup speech recognition, timers, and audio streams on unmount
  useEffect(() => {
    return () => {
      stopSpeech();
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      if (noSpeechTimeoutRef.current) clearTimeout(noSpeechTimeoutRef.current);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [stopSpeech]);

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
    stopSpeech();
    const newId = `chat_${Date.now()}`;
    const initialGreeting: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: "assistant",
      text: isHi
        ? "नमस्ते! मैं आपका योजनसेतु AI सहायक हूँ।\n\nआपके लिए 100% सही और सबसे अधिक लाभदायक सरकारी योजनाएं खोजने के लिए, मुझे पहले आपके बारे में कुछ बुनियादी बातें जाननी होंगी।\n\n👉 **कृपया बताएं: आपकी उम्र (आयु) क्या है और आप क्या काम करते हैं?** (जैसे: किसान, छात्र, वरिष्ठ नागरिक, छोटा व्यापारी, दैनिक श्रमिक, या गृहिणी?)"
        : "Hello! I am your YojanSetu AI Assistant.\n\nTo find the exact government welfare schemes and financial benefits tailored for you, I need to know a little about you first.\n\n👉 **Please tell me: What is your current age and what is your primary profession or role?** (e.g. Farmer, Student, Senior Citizen, Small Business, Laborer, or Homemaker?)",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      confidenceScore: 0.15,
      confidenceLevel: "LOW",
      followUpQuestion: {
        question_id: "ask_identity_and_role",
        field: "occupation",
        question_hi: "कृपया अपना मुख्य कार्य या भूमिका चुनें:",
        question_en: "Please select your primary role or category:",
        rationale_hi: "सरकारी योजनाएं नागरिक की उम्र और व्यवसाय के आधार पर निर्धारित होती हैं।",
        rationale_en: "Government schemes are strictly based on citizen age and occupation.",
        options: [
          { label_hi: "🌾 किसान / कृषक", label_en: "Farmer", value: { occupation: "FARMER" } },
          { label_hi: "🎓 विद्यार्थी / छात्र", label_en: "Student", value: { occupation: "STUDENT" } },
          { label_hi: "👴 वरिष्ठ नागरिक (60+ वर्ष)", label_en: "Senior Citizen (60+)", value: { age: 60 } },
          { label_hi: "💼 छोटा व्यापारी / स्वरोजगार", label_en: "Self-Employed / Shop", value: { occupation: "SELF_EMPLOYED" } },
          { label_hi: "👩 गृहिणी / महिला", label_en: "Homemaker / Women", value: { gender: "FEMALE", occupation: "HOMEMAKER" } },
          { label_hi: "🔨 दैनिक श्रमिक / मजदूर", label_en: "Daily Wage Worker", value: { occupation: "LABORER" } },
        ],
      },
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

  // Clear or reset the active chat immediately
  const handleClearCurrentChat = () => {
    if (activeSessionId) {
      handleDeleteSession(activeSessionId);
    } else {
      startNewChat();
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

    if (customQuery === undefined) {
      lastInputWasVoiceRef.current = false;
    }

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

    // Dynamically extract demographic entities from the user query
    const extracted = extractDemographicsFromText(query);
    let activeParams = parameters;
    if (Object.keys(extracted).length > 0) {
      activeParams = {
        ...parameters,
        ...extracted,
      };
      setParameters(activeParams);
      const keys = Object.keys(extracted);
      if (keys.length > 0) {
        setLastUpdatedField(keys[0]);
      }
    }

    try {
      const context = {
        ...getContextFromParameters(activeParams),
        turnCount: updatedMessages.length,
      };
      const resp: AgentQueryResponse = await sendAgentQuery(
        query,
        context,
        lang === "hi" ? "hi" : "en",
        updatedMessages
      );

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: "assistant",
        text: resp.final_answer || (isHi ? "यहाँ आपकी पात्रता और योजनाओं की जानकारी है।" : "Here is your eligibility and scheme information."),
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        schemes: resp.structured_data?.recommended_schemes || [],
        candidateSchemes: resp.structured_data?.candidate_schemes || [],
        documents: resp.structured_data?.required_documents || [],
        citations: resp.structured_data?.citations || [],
        kioskInfo: resp.structured_data?.emitra_kiosk_info,
        reasoningSteps: resp.steps || [],
        confidenceScore: resp.structured_data?.confidence_score,
        confidenceLevel: resp.structured_data?.confidence_level,
        followUpQuestion: resp.structured_data?.follow_up_question || null,
      };

      const finalMessages = [...updatedMessages, assistantMsg];
      setMessages(finalMessages);
      persistSession(
        currentSession,
        finalMessages,
        parameters,
        isFirstQuery ? query : undefined
      );

      // If voice input was used by the citizen, speak the reply aloud automatically!
      if (lastInputWasVoiceRef.current) {
        speakText(assistantMsg.text, assistantMsg.id);
        lastInputWasVoiceRef.current = false;
      }
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
    const detailsHi: string[] = [];
    if (newParams.age !== null) detailsHi.push(`उम्र ${newParams.age} वर्ष`);
    if (newParams.gender) detailsHi.push(newParams.gender === "FEMALE" ? "महिला" : newParams.gender === "MALE" ? "पुरुष" : "अन्य");
    if (newParams.category) detailsHi.push(`${newParams.category} श्रेणी`);
    if (newParams.income !== null) detailsHi.push(`वार्षिक आय ₹${newParams.income.toLocaleString("en-IN")}`);
    if (newParams.occupation) detailsHi.push(`व्यवसाय ${newParams.occupation}`);
    if (newParams.district) detailsHi.push(`जिला ${newParams.district}`);
    if (newParams.landBigha !== null && newParams.landBigha > 0) detailsHi.push(`भूमि ${newParams.landBigha} बीघा`);
    if (newParams.isWidow) detailsHi.push("एकल नारी/विधवा");
    if (newParams.isDisabled) detailsHi.push("दिव्यांग");

    const query = isHi
      ? `मेरी प्रोफाइल: ${detailsHi.join(", ") || "सामान्य नागरिक"}। मुझे किन सरकारी योजनाओं का लाभ मिलेगा?`
      : `My profile: ${detailsHi.join(", ") || "citizen"}. What government schemes and pensions am I eligible for?`;

    handleSendMessage(query);
  };

  // Voice Auto-Send Trigger (dispatched on silence or manual stop)
  const triggerVoiceAutoSend = useCallback(() => {
    if (hasSentRef.current) return;
    const textToSend = speechTextRef.current.trim();

    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (noSpeechTimeoutRef.current) {
      clearTimeout(noSpeechTimeoutRef.current);
      noSpeechTimeoutRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }

    isListeningRef.current = false;
    setIsListening(false);
    setSpeechStatus("idle");

    if (textToSend.length > 0) {
      hasSentRef.current = true;
      lastInputWasVoiceRef.current = true;
      setInputText("");
      speechTextRef.current = "";
      // Immediately send query into chat without user needing to press Enter
      handleSendMessageRef.current?.(textToSend);
    }
  }, []);

  // Stop voice listening cleanly
  const stopVoiceListening = useCallback(
    (shouldSend: boolean = true) => {
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      if (noSpeechTimeoutRef.current) {
        clearTimeout(noSpeechTimeoutRef.current);
        noSpeechTimeoutRef.current = null;
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {}
      }
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((track) => track.stop());
        audioStreamRef.current = null;
      }

      isListeningRef.current = false;
      setIsListening(false);
      setSpeechStatus("idle");

      const textToSend = speechTextRef.current.trim();
      if (shouldSend && textToSend.length > 0 && !hasSentRef.current) {
        hasSentRef.current = true;
        lastInputWasVoiceRef.current = true;
        setInputText("");
        speechTextRef.current = "";
        handleSendMessageRef.current?.(textToSend);
      } else {
        speechTextRef.current = "";
      }
    },
    []
  );

  // Toggle voice recognition with mic permission preflight, continuous capture, and autosend
  const toggleVoice = async () => {
    stopSpeech(); // Stop any active assistant speech immediately when microphone is tapped

    if (isListeningRef.current) {
      // User tapped stop button: if speech text is present, immediately auto-send!
      stopVoiceListening(true);
      return;
    }

    if (isProcessingRef.current) {
      setSpeechError(
        isHi
          ? "कृपया पहले पिछले प्रश्न का उत्तर आने तक प्रतीक्षा करें।"
          : "Please wait for current response to complete before speaking."
      );
      setTimeout(() => setSpeechError(null), 3000);
      return;
    }

    setSpeechError(null);
    hasSentRef.current = false;
    speechTextRef.current = "";

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setSpeechError(
        isHi
          ? "इस ब्राउज़र में स्पीच रिकग्निशन उपलब्ध नहीं है। कृपया Google Chrome या Microsoft Edge का उपयोग करें।"
          : "Speech recognition is not supported in this browser. Please use Chrome or Edge."
      );
      setTimeout(() => setSpeechError(null), 5000);
      return;
    }

    // 1. Prompt / verify microphone permissions explicitly
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Immediately release stream tracks so SpeechRecognition has dedicated microphone access
        stream.getTracks().forEach((track) => track.stop());
      } catch (micErr: any) {
        console.warn("Microphone access check failed:", micErr);
        if (micErr.name === "NotAllowedError" || micErr.name === "PermissionDeniedError") {
          setSpeechError(
            isHi
              ? "माइक्रोफ़ोन अनुमति अस्वीकृत है। कृपया ब्राउज़र सेटिंग्स में माइक्रोफ़ोन की अनुमति दें।"
              : "Microphone permission denied. Please allow microphone access in your browser."
          );
        } else if (micErr.name === "NotFoundError" || micErr.name === "DevicesNotFoundError") {
          setSpeechError(
            isHi
              ? "कोई माइक्रोफ़ोन डिवाइस नहीं मिला। कृपया माइक कनेक्ट करें।"
              : "No microphone device found. Please connect a microphone."
          );
        } else {
          setSpeechError(
            isHi
              ? "माइक्रोफ़ोन एक्सेस करने में समस्या आई। पुनः प्रयास करें।"
              : "Could not access microphone. Please try again."
          );
        }
        setTimeout(() => setSpeechError(null), 4000);
        return;
      }
    }

    // 2. Initialize SpeechRecognition instance with continuous stream
    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = voiceLang === "hi" ? "hi-IN" : "en-IN";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        isListeningRef.current = true;
        setIsListening(true);
        setSpeechStatus("listening");

        // 10s idle safety timer if citizen doesn't say anything
        if (noSpeechTimeoutRef.current) clearTimeout(noSpeechTimeoutRef.current);
        noSpeechTimeoutRef.current = setTimeout(() => {
          if (isListeningRef.current && !speechTextRef.current.trim()) {
            stopVoiceListening(false);
            setSpeechError(
              isHi
                ? "कोई आवाज नहीं सुनाई दी। पुनः माइक दबाकर बोलें।"
                : "No voice detected. Click the mic to try speaking again."
            );
            setTimeout(() => setSpeechError(null), 4000);
          }
        }, 10000);
      };

      recognition.onresult = (event: any) => {
        // Clear idle no-speech timeout once speech arrives
        if (noSpeechTimeoutRef.current) {
          clearTimeout(noSpeechTimeoutRef.current);
          noSpeechTimeoutRef.current = null;
        }

        let interim = "";
        let final = "";
        for (let i = 0; i < event.results.length; i++) {
          const item = event.results[i];
          if (item.isFinal) {
            final += item[0].transcript + " ";
          } else {
            interim += item[0].transcript;
          }
        }

        const combined = (final + interim).trim();
        if (!combined) return;

        speechTextRef.current = combined;
        setInputText(combined);
        setSpeechStatus("hearing");

        // Dynamically extract demographics as user speaks
        const liveEntities = extractDemographicsFromText(combined);
        if (Object.keys(liveEntities).length > 0) {
          setParameters((prev) => ({
            ...prev,
            ...liveEntities,
          }));
          const keys = Object.keys(liveEntities);
          if (keys.length > 0) {
            setLastUpdatedField(keys[0]);
          }
        }

        // Silence Debounce: When citizen stops speaking for 1.6s, automatically send!
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
        }
        silenceTimerRef.current = setTimeout(() => {
          if (isListeningRef.current && speechTextRef.current.trim()) {
            setSpeechStatus("sending");
            triggerVoiceAutoSend();
          }
        }, 1600);
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition event error:", event.error);
        if (event.error === "no-speech") {
          // Do NOT abort if user paused briefly mid-sentence!
          return;
        }
        if (event.error === "aborted") {
          return;
        }
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          stopVoiceListening(false);
          setSpeechError(
            isHi
              ? "माइक्रोफ़ोन अनुमति अस्वीकृत है। कृपया ब्राउज़र में अनुमति दें।"
              : "Microphone permission denied. Please allow microphone in browser."
          );
          setTimeout(() => setSpeechError(null), 4000);
          return;
        }

        // If text was already captured before error, auto-send it
        if (speechTextRef.current.trim() && !hasSentRef.current) {
          triggerVoiceAutoSend();
        } else {
          stopVoiceListening(false);
          setSpeechError(
            isHi
              ? "आवाज नहीं पहचानी जा सकी। कृपया पुनः प्रयास करें।"
              : "Could not recognize audio clearly. Please try again."
          );
          setTimeout(() => setSpeechError(null), 3000);
        }
      };

      recognition.onend = () => {
        if (isListeningRef.current) {
          if (speechTextRef.current.trim() && !hasSentRef.current) {
            // Natural speech termination -> AUTO SEND!
            triggerVoiceAutoSend();
          } else if (!hasSentRef.current) {
            // Re-trigger if continuous mode disconnected without text
            try {
              recognition.start();
            } catch {
              isListeningRef.current = false;
              setIsListening(false);
              setSpeechStatus("idle");
            }
          }
        }
      };

      recognition.start();
    } catch (err: any) {
      console.error("Speech initialization error:", err);
      stopVoiceListening(false);
      setSpeechError(
        isHi
          ? "माइक्रोफ़ोन प्रारंभ नहीं हो सका। कृपया पुनः प्रयास करें।"
          : "Could not start microphone. Please try again."
      );
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
          {/* Clear Current Chat Button */}
          <button
            type="button"
            onClick={handleClearCurrentChat}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-bold text-slate-600 hover:text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition cursor-pointer"
            title={isHi ? "वर्तमान बातचीत हटाएं / नया चैट" : "Clear conversation"}
          >
            <span>🗑️</span>
            <span className="hidden sm:inline">
              {isHi ? "चैट हटाएं" : "Clear Chat"}
            </span>
          </button>

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
                    {/* Confidence Score Pill & Speaker Button for Assistant Messages */}
                    {!isUser && (
                      <div className="flex items-center justify-between gap-2 mb-2">
                        {msg.confidenceScore !== undefined ? (
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border ${
                              msg.confidenceScore >= 0.8
                                ? "bg-emerald-50 text-emerald-800 border-emerald-300 shadow-2xs"
                                : msg.confidenceScore >= 0.5
                                ? "bg-amber-50 text-amber-800 border-amber-300 shadow-2xs"
                                : "bg-slate-100 text-slate-700 border-slate-300"
                            }`}
                          >
                            <span>{msg.confidenceScore >= 0.8 ? "🔒" : "⏳"}</span>
                            <span>
                              {msg.confidenceScore >= 0.8
                                ? isHi
                                  ? "100% सत्यापित व पुष्ट पात्रता"
                                  : "100% Confident Match"
                                : isHi
                                ? `सत्यापन प्रक्रियाधीन (${Math.round(msg.confidenceScore * 100)}% सटीकता)`
                                : `Verification in Progress (${Math.round(msg.confidenceScore * 100)}% Confidence)`}
                            </span>
                          </span>
                        ) : (
                          <span />
                        )}

                        {/* Speaker Read Aloud Button */}
                        <button
                          type="button"
                          onClick={() => {
                            if (speakingMsgId === msg.id) {
                              stopSpeech();
                            } else {
                              speakText(msg.text, msg.id);
                            }
                          }}
                          className={`px-2 py-0.5 rounded-md text-[11px] font-bold flex items-center gap-1 transition cursor-pointer ${
                            speakingMsgId === msg.id
                              ? "bg-rose-100 text-rose-700 border border-rose-300 animate-pulse shadow-xs"
                              : "bg-white hover:bg-orange-50 text-slate-600 hover:text-orange-700 border border-slate-200 shadow-2xs"
                          }`}
                          title={
                            speakingMsgId === msg.id
                              ? isHi
                                ? "आवाज़ बंद करें (Stop audio)"
                                : "Stop audio"
                              : isHi
                              ? "बोलकर सुनाएं (Read aloud)"
                              : "Read aloud"
                          }
                        >
                          <span>{speakingMsgId === msg.id ? "⏹️" : "🔊"}</span>
                          <span>{speakingMsgId === msg.id ? (isHi ? "रोकें" : "Stop") : (isHi ? "सुनें" : "Listen")}</span>
                        </button>
                      </div>
                    )}

                    {/* Message Text */}
                    <div className="whitespace-pre-wrap font-medium">{msg.text}</div>

                    {/* Interactive Follow-Up Question Card */}
                    {msg.followUpQuestion && (
                      <div className="mt-3.5 p-3.5 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50/80 border border-amber-300 shadow-sm space-y-2.5">
                        <p className="font-bold text-slate-900 text-xs sm:text-sm leading-snug flex items-start gap-2">
                          <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center text-white text-[10px]">?</span>
                          <span>{isHi ? msg.followUpQuestion.question_hi : msg.followUpQuestion.question_en}</span>
                        </p>
                        {msg.followUpQuestion.rationale_hi && (
                          <p className="text-[11px] text-amber-700/80 italic pl-6">
                            ℹ️ {isHi ? msg.followUpQuestion.rationale_hi : msg.followUpQuestion.rationale_en}
                          </p>
                        )}

                        {/* Quick Interactive Clickable Option Buttons */}
                        {msg.followUpQuestion.options && msg.followUpQuestion.options.length > 0 && (
                          <div className="pt-1 flex flex-wrap gap-1.5">
                            {msg.followUpQuestion.options.map((opt, i) => (
                              <button
                                key={i}
                                type="button"
                                onClick={() => {
                                  if (opt.value) {
                                    setParameters((prev) => ({
                                      ...prev,
                                      ...opt.value,
                                    }));
                                    const keys = Object.keys(opt.value);
                                    if (keys.length > 0) setLastUpdatedField(keys[0]);
                                  }
                                  const answerText = isHi ? opt.label_hi : opt.label_en;
                                  handleSendMessage(answerText);
                                }}
                                className="px-3 py-1.5 rounded-lg bg-white hover:bg-orange-600 hover:text-white text-slate-800 font-bold text-xs border border-amber-300 shadow-2xs hover:shadow-xs transition-all active:scale-95 cursor-pointer flex items-center gap-1.5"
                              >
                                <span>👉</span>
                                <span>{isHi ? opt.label_hi : opt.label_en}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Candidate Schemes under verification */}
                    {msg.candidateSchemes && msg.candidateSchemes.length > 0 && (!msg.schemes || msg.schemes.length === 0) && msg.confidenceScore !== undefined && msg.confidenceScore >= 0.5 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-200 space-y-1.5">
                        <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1">
                          <span>💡</span>
                          <span>{isHi ? "संभावित योजनाएं (सत्यापन जारी):" : "Potential Schemes Under Evaluation:"}</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.candidateSchemes.map((cs, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-[11px] font-semibold"
                            >
                              {isHi ? cs.name_hi : cs.name_en}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

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
          {/* Active Voice Listening Banner with Auto-Send and Language Selector */}
          {isListening && (
            <div className="px-3 sm:px-4 py-2 bg-gradient-to-r from-orange-50 via-rose-50 to-orange-50 border-t border-orange-200/80 flex items-center justify-between gap-2 text-xs sm:text-sm shadow-xs animate-fadeIn">
              <div className="flex items-center gap-2 text-slate-700 font-medium overflow-hidden">
                <span className="flex h-3 w-3 relative flex-shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
                </span>
                {speechStatus === "sending" ? (
                  <span className="text-orange-700 font-bold flex items-center gap-1.5 animate-pulse">
                    <span>🚀</span> {isHi ? "स्वतः भेजा जा रहा है..." : "Auto-sending query..."}
                  </span>
                ) : speechTextRef.current ? (
                  <span className="text-slate-800 flex items-center gap-1.5 truncate">
                    <span className="font-semibold text-rose-600 flex-shrink-0">
                      {isHi ? "पहचाना:" : "Heard:"}
                    </span>
                    <span className="italic truncate max-w-[180px] sm:max-w-xs text-slate-900 font-semibold">
                      &quot;{speechTextRef.current}&quot;
                    </span>
                    <span className="text-[11px] text-orange-600 font-normal hidden sm:inline flex-shrink-0">
                      ({isHi ? "रुकते ही स्वतः भेजा जाएगा" : "auto-sends when you pause"})
                    </span>
                  </span>
                ) : (
                  <span className="text-slate-700 flex items-center gap-1.5">
                    <span>🎙️</span>{" "}
                    {isHi
                      ? "बोलिए, मैं सुन रहा हूँ... (बोलना रुकते ही स्वतः भेजा जाएगा)"
                      : "Listening... speak now (will auto-send when you pause)"}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5 flex-shrink-0">
                {/* Voice Language Switcher */}
                <button
                  type="button"
                  onClick={() => {
                    const nextLang = voiceLang === "hi" ? "en" : "hi";
                    setVoiceLang(nextLang);
                    if (recognitionRef.current) {
                      try {
                        recognitionRef.current.stop();
                      } catch {}
                    }
                  }}
                  className="px-2 py-0.5 text-[11px] sm:text-xs font-semibold rounded-md bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition shadow-2xs"
                  title={isHi ? "आवाज भाषा बदलें" : "Switch voice language"}
                >
                  🗣️ {voiceLang === "hi" ? "हिंदी" : "English"}
                </button>

                {/* Cancel Voice Input */}
                <button
                  type="button"
                  onClick={() => stopVoiceListening(false)}
                  className="text-xs text-slate-400 hover:text-rose-600 font-bold px-1.5 py-0.5 rounded transition"
                  title={isHi ? "रद्द करें" : "Cancel"}
                >
                  ✕
                </button>
              </div>
            </div>
          )}

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

          {/* Active Text-To-Speech Speaking Banner */}
          {speakingMsgId && (
            <div className="px-4 py-2 bg-gradient-to-r from-orange-600 to-amber-600 text-white flex items-center justify-between text-xs font-bold shadow-md flex-shrink-0 animate-in fade-in duration-200">
              <div className="flex items-center gap-2">
                <span className="text-base animate-bounce">🔊</span>
                <span>{isHi ? "योजनसेतु AI उत्तर बोलकर सुना रहा है..." : "YojanSetu AI is speaking aloud..."}</span>
                <span className="flex gap-0.5 items-end h-3 ml-1">
                  <span className="w-1 bg-white animate-pulse h-3 rounded-full"></span>
                  <span className="w-1 bg-white animate-pulse h-2 rounded-full delay-75"></span>
                  <span className="w-1 bg-white animate-pulse h-3.5 rounded-full delay-150"></span>
                </span>
              </div>
              <button
                type="button"
                onClick={stopSpeech}
                className="px-2.5 py-1 rounded-lg bg-white/20 hover:bg-white text-white hover:text-orange-900 text-xs font-bold transition shadow-xs cursor-pointer flex items-center gap-1"
                title={isHi ? "आवाज़ बंद करें" : "Stop speaking"}
              >
                <span>⏹️</span>
                <span>{isHi ? "आवाज़ बंद करें" : "Stop Audio"}</span>
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
                      ? "बोलना पूरा हुआ (तुरंत भेजें)"
                      : "Done speaking (Send now)"
                    : isHi
                    ? "बोलकर पूछें (स्वतः भेजा जाएगा)"
                    : "Speak your query (Auto-sends)"
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
                      ? "सुन रहा हूँ... बोलिए (रुकते ही स्वतः भेजा जाएगा)..."
                      : "Listening... speak now (auto-sends when you pause)..."
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
          lastUpdatedField={lastUpdatedField}
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
          district={parameters.district ?? undefined}
          age={parameters.age ?? undefined}
          gender={parameters.gender ?? undefined}
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
