'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  CitizenLanguage,
  CitizenQuestionDisplay,
  CitizenSchemeCard,
  CitizenSchemeDetail,
  SessionSummary,
  ConversationTurnResponse,
} from '@/types/citizen';
import {
  createCitizenSession,
  getCitizenSession,
  getCitizenProfile,
  updateCitizenProfile,
  declineCitizenField,
  discoverCitizenSchemes,
  deleteCitizenSession,
  getCitizenSchemeDetail,
  sendConversationTurn,
  getConversationState,
  startOverConversation,
  endConversation,
  sendAgentQuery,
  ApiError,
} from '@/lib/api';
import { AgentQueryResponse, SchemeCitation, RecommendedScheme, RequiredDocument, EmitraKioskInfo } from '@/types/agent';

import CitizenShell from '@/components/citizen/CitizenShell';
import NeedInput from '@/components/citizen/NeedInput';
import QuestionCard from '@/components/citizen/QuestionCard';
import ConfirmationCard from '@/components/citizen/ConfirmationCard';
import ClarificationCard from '@/components/citizen/ClarificationCard';
import ResultsList from '@/components/citizen/ResultsList';
import ProfileSummary from '@/components/citizen/ProfileSummary';
import SchemeDetails from '@/components/citizen/SchemeDetails';
import { VoiceMode } from '@/components/voice/VoiceMode';

import PersonaPicker, { PersonaData, PRESET_PERSONAS } from '@/components/citizen/PersonaPicker';
import EligibilitySimulator from '@/components/citizen/EligibilitySimulator';
import AgentReasoningTrace from '@/components/citizen/AgentReasoningTrace';
import CitationDrawer from '@/components/citizen/CitationDrawer';
import EmitraSlipModal from '@/components/citizen/EmitraSlipModal';

type ModeType = 'AGENT' | 'SIMULATOR' | 'GUIDED' | 'VOICE';

type FlowState =
  | 'START'
  | 'COLLECTING_INFORMATION'
  | 'CONFIRMATION'
  | 'CLARIFICATION'
  | 'LOADING'
  | 'RESULTS'
  | 'NO_RESULTS'
  | 'CANNOT_RESOLVE'
  | 'COMPLETED'
  | 'ERROR'
  | 'SESSION_EXPIRED';

const STORAGE_SESSION_KEY = 'yojansetu_citizen_session_id';

export default function CitizenPage() {
  const [language, setLanguage] = useState<CitizenLanguage>('hi');
  const [activeMode, setActiveMode] = useState<ModeType>('AGENT');
  const [flowState, setFlowState] = useState<FlowState>('START');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [citizenProfile, setCitizenProfile] = useState<Record<string, any>>({});
  const [needText, setNeedText] = useState<string>('');
  const [nextQuestion, setNextQuestion] = useState<CitizenQuestionDisplay | null>(null);
  const [eligibleSchemes, setEligibleSchemes] = useState<CitizenSchemeCard[]>([]);
  const [moreInfoSchemes, setMoreInfoSchemes] = useState<CitizenSchemeCard[]>([]);

  // Agent State
  const [agentQueryText, setAgentQueryText] = useState<string>('');
  const [agentResponse, setAgentResponse] = useState<AgentQueryResponse | null>(null);
  const [isAgentRunning, setIsAgentRunning] = useState<boolean>(false);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<SchemeCitation | null>(null);
  const [isEmitraSlipOpen, setIsEmitraSlipOpen] = useState<boolean>(false);
  const [agentContext, setAgentContext] = useState<Record<string, any>>({});

  // Conversation turn state
  const [currentConversation, setCurrentConversation] = useState<ConversationTurnResponse | null>(null);
  const [infoBanner, setInfoBanner] = useState<{ text_hi: string; text_en: string } | null>(null);

  // Scheme detail modal state
  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [schemeDetail, setSchemeDetail] = useState<CitizenSchemeDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Status & error states
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const requestIdRef = useRef<number>(0);

  const isHi = language === 'hi';

  // Helper: map ConversationTurnResponse to UI states
  const applyConversationResponse = useCallback((resp: ConversationTurnResponse) => {
    setCurrentConversation(resp);

    if (resp.results) {
      setEligibleSchemes(resp.results.eligible || []);
      setMoreInfoSchemes(resp.results.more_information_required || []);
    }

    if (resp.action === 'ANSWER_FIELD_HELP' || resp.action === 'ANSWER_SCHEME_QUERY') {
      setInfoBanner({
        text_hi: resp.message.text_hi,
        text_en: resp.message.text_en,
      });
    } else {
      setInfoBanner(null);
    }

    if (resp.action === 'CONFIRM_PROFILE_VALUE') {
      setFlowState('CONFIRMATION');
    } else if (resp.action === 'CLARIFY_PROFILE_VALUE') {
      setFlowState('CLARIFICATION');
    } else if (resp.action === 'ASK_PROFILE_FIELD') {
      const inp = resp.expected_input;
      const dataTypeMap: Record<string, any> = {
        NUMBER: 'integer',
        CURRENCY: 'currency',
        BOOLEAN: 'boolean',
        SELECT: 'select',
        DISTRICT: 'select',
        TEXT: 'string',
      };
      setNextQuestion({
        field: inp.field || 'information',
        reason_code: 'DETERMINISTIC_SELECTOR',
        data_type: dataTypeMap[inp.type] || 'string',
        display_name_en: inp.field || 'Information',
        display_name_hi: inp.field || 'जानकारी',
        question_en: resp.message.text_en,
        question_hi: resp.message.text_hi,
        options: inp.options?.map((o) => ({
          value: String(o.value),
          label_en: o.label_en,
          label_hi: o.label_hi,
        })) || null,
        unit_en: inp.unit_en,
        unit_hi: inp.unit_hi,
        sensitivity_level: 'LOW',
        allow_decline: inp.allow_decline ?? true,
      });
      setFlowState('COLLECTING_INFORMATION');
    } else if (resp.action === 'SHOW_RESULTS') {
      setFlowState('RESULTS');
    } else if (resp.action === 'SHOW_NO_RESULTS' || resp.state === 'NO_RESULTS') {
      setFlowState('NO_RESULTS');
    } else if (resp.action === 'SHOW_CANNOT_RESOLVE' || resp.state === 'CANNOT_RESOLVE') {
      setFlowState('CANNOT_RESOLVE');
    } else if (resp.action === 'END_CONVERSATION' || resp.state === 'COMPLETED') {
      setFlowState('COMPLETED');
    } else if (resp.action === 'ASK_NEED' || resp.state === 'WAITING_FOR_NEED') {
      setFlowState('START');
    }
  }, []);

  // 1. Session Restoration on Mount
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const storedId = sessionStorage.getItem(STORAGE_SESSION_KEY);
        if (!storedId) return;

        setIsProcessing(true);
        const summary = await getCitizenSession(storedId);
        setSessionId(storedId);
        setSessionSummary(summary);

        try {
          const prof = await getCitizenProfile(storedId);
          setCitizenProfile(prof.profile || {});
        } catch {}

        try {
          const stateResp = await getConversationState(storedId);
          if (stateResp) {
            applyConversationResponse(stateResp);
          }
        } catch {}
      } catch (err: any) {
        sessionStorage.removeItem(STORAGE_SESSION_KEY);
        setSessionId(null);
      } finally {
        setIsProcessing(false);
      }
    };

    restoreSession();
  }, [applyConversationResponse]);

  // Ensure active session when voice mode is selected
  useEffect(() => {
    if (activeMode === 'VOICE' && !sessionId && !isProcessing) {
      const initVoiceSession = async () => {
        try {
          setIsProcessing(true);
          const s = await createCitizenSession();
          setSessionId(s.session_id);
          sessionStorage.setItem(STORAGE_SESSION_KEY, s.session_id);
        } catch (err: any) {
          console.warn('Voice session auto-init local fallback:', err);
          const fallbackId = `sess_local_${Date.now()}`;
          setSessionId(fallbackId);
          sessionStorage.setItem(STORAGE_SESSION_KEY, fallbackId);
        } finally {
          setIsProcessing(false);
        }
      };
      initVoiceSession();
    }
  }, [activeMode, sessionId, isProcessing]);

  // Execute ReAct Agent Query
  const handleRunAgent = async (customQuery?: string, customContext?: Record<string, any>) => {
    const query = (customQuery || agentQueryText || '').trim();
    if (!query) return;

    setIsAgentRunning(true);
    setErrorMessage(null);
    const ctx = customContext || agentContext || {};

    try {
      const resp = await sendAgentQuery(query, ctx, language);
      setAgentResponse(resp);
    } catch (err: any) {
      console.error('Agent query failed:', err);
      setErrorMessage(
        isHi
          ? 'एजेंट से संपर्क करने में समस्या आई। कृपया पुनः प्रयास करें।'
          : 'Agent execution failed. Please verify the backend connection.'
      );
    } finally {
      setIsAgentRunning(false);
    }
  };

  // Select Persona Shortcut
  const handleSelectPersona = (persona: PersonaData) => {
    setSelectedPersonaId(persona.id);
    const q = isHi ? persona.query_hi : persona.query_en;
    setAgentQueryText(q);
    setAgentContext(persona.context);
    setActiveMode('AGENT');
    handleRunAgent(q, persona.context);
  };

  // Simulator apply to agent
  const handleApplySimulatorToAgent = (params: {
    age: number;
    income: number;
    landBigha: number;
    category: string;
    gender: string;
    isWidow: boolean;
    isStudent: boolean;
    isDisabled: boolean;
    hasJanAadhaar: boolean;
  }) => {
    const ctx: Record<string, any> = {
      age: params.age,
      annual_income: params.income,
      land_area_bigha: params.landBigha,
      social_category: params.category,
      gender: params.gender,
      is_widow: params.isWidow,
      student_status: params.isStudent ? 'ENROLLED' : 'NONE',
      is_disabled: params.isDisabled,
      has_jan_aadhaar: params.hasJanAadhaar,
      district: 'Rajasthan',
    };

    const query = isHi
      ? `मेरी उम्र ${params.age} वर्ष है, लिंग ${params.gender === 'FEMALE' ? 'महिला' : 'पुरुष'}, वार्षिक आय ₹${params.income.toLocaleString('en-IN')}, कृषि भूमि ${params.landBigha} बीघा है। मुझे किन योजनाओं का लाभ मिलेगा?`
      : `I am ${params.age} years old ${params.gender.toLowerCase()}, earning ₹${params.income.toLocaleString('en-IN')} annually with ${params.landBigha} bighas land. What government schemes and pensions am I eligible for?`;

    setAgentQueryText(query);
    setAgentContext(ctx);
    setSelectedPersonaId(null);
    setActiveMode('AGENT');
    handleRunAgent(query, ctx);
  };

  // Handle Guided need submission
  const handleSubmitNeed = async (need: string) => {
    if (!need.trim() || isProcessing) return;
    setIsProcessing(true);
    setErrorMessage(null);
    setNeedText(need);

    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const newSession = await createCitizenSession();
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        sessionStorage.setItem(STORAGE_SESSION_KEY, currentSessionId);
      }

      const resp = await sendConversationTurn(currentSessionId, {
        type: 'TEXT',
        text: need,
      });

      applyConversationResponse(resp);
    } catch (err: any) {
      setErrorMessage(
        isHi ? 'खोज प्रारंभ करने में समस्या आई। कृपया पुनः प्रयास करें।' : 'Failed to start query.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  // Start Over
  const handleStartOver = async () => {
    setIsProcessing(true);
    setAgentResponse(null);
    setAgentQueryText('');
    setSelectedPersonaId(null);
    try {
      if (sessionId) {
        await startOverConversation(sessionId);
      }
    } catch {}
    sessionStorage.removeItem(STORAGE_SESSION_KEY);
    setSessionId(null);
    setSessionSummary(null);
    setCitizenProfile({});
    setEligibleSchemes([]);
    setMoreInfoSchemes([]);
    setNextQuestion(null);
    setCurrentConversation(null);
    setInfoBanner(null);
    setFlowState('START');
    setIsProcessing(false);
  };

  // Handle Scheme Detail View
  const handleViewDetails = async (schemeId: string) => {
    setSelectedSchemeId(schemeId);
    setLoadingDetail(true);
    setDetailError(null);
    try {
      const detail = await getCitizenSchemeDetail(schemeId, language);
      setSchemeDetail(detail);
    } catch (err: any) {
      setDetailError(isHi ? 'योजना का विवरण लोड करने में असमर्थ।' : 'Could not load details.');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedSchemeId(null);
    setSchemeDetail(null);
    setDetailError(null);
  };

  return (
    <CitizenShell
      lang={language}
      onLanguageChange={(newLang) => setLanguage(newLang)}
      onResetSession={handleStartOver}
      hasActiveSession={Boolean(sessionId || agentResponse)}
      isResetting={isProcessing}
    >
      <div className="space-y-6">
        {/* Flagship Mode Navigation Bar */}
        <div className="bg-white rounded-2xl p-2 border border-slate-200 shadow-xs flex flex-wrap gap-1.5 sm:gap-2">
          <button
            type="button"
            onClick={() => setActiveMode('AGENT')}
            className={`flex-1 min-w-[140px] py-2.5 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
              activeMode === 'AGENT'
                ? 'bg-orange-600 text-white shadow-sm shadow-orange-600/30'
                : 'text-slate-700 hover:bg-slate-100'
            }`}
          >
            <span>⚡</span>
            <span>{isHi ? 'AI रीज़निंग एजेंट' : 'AI ReAct Agent'}</span>
            <span className="hidden sm:inline text-[10px] opacity-80 font-normal">
              (Zero Hallucination)
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMode('SIMULATOR')}
            className={`flex-1 min-w-[140px] py-2.5 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
              activeMode === 'SIMULATOR'
                ? 'bg-amber-600 text-white shadow-sm shadow-amber-600/30'
                : 'text-slate-700 hover:bg-slate-100'
            }`}
          >
            <span>🎛️</span>
            <span>{isHi ? 'पात्रता सिम्युलेटर' : 'Live Simulator'}</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMode('GUIDED')}
            className={`flex-1 min-w-[120px] py-2.5 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
              activeMode === 'GUIDED'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-700 hover:bg-slate-100'
            }`}
          >
            <span>💬</span>
            <span>{isHi ? 'मार्गदर्शित प्रश्नावली' : 'Guided Flow'}</span>
          </button>

          <button
            type="button"
            onClick={async () => {
              setActiveMode('VOICE');
              if (!sessionId) {
                try {
                  setIsProcessing(true);
                  const s = await createCitizenSession();
                  setSessionId(s.session_id);
                  sessionStorage.setItem(STORAGE_SESSION_KEY, s.session_id);
                } catch (err: any) {
                  const fallbackId = `sess_local_${Date.now()}`;
                  setSessionId(fallbackId);
                  sessionStorage.setItem(STORAGE_SESSION_KEY, fallbackId);
                } finally {
                  setIsProcessing(false);
                }
              }
            }}
            className={`flex-1 min-w-[110px] py-2.5 px-3 rounded-xl font-bold text-xs transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
              activeMode === 'VOICE'
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'text-slate-700 hover:bg-slate-100'
            }`}
          >
            <span>🎙️</span>
            <span>{isHi ? 'आवाज़ सहायक' : 'Voice Mode'}</span>
          </button>
        </div>

        {/* Error notification banner */}
        {errorMessage && (
          <div
            role="alert"
            className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-sm flex items-center justify-between"
          >
            <span>{errorMessage}</span>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-500 hover:text-rose-700 font-bold ml-3 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* MODE 1: AI REACT AGENT (Zero Hallucination + Official Gazette) */}
        {/* ------------------------------------------------------------- */}
        {activeMode === 'AGENT' && (
          <div className="space-y-6">
            {/* 1-Click Citizen Personas for Evaluators & Demoers */}
            <PersonaPicker
              language={language}
              onSelectPersona={handleSelectPersona}
              selectedPersonaId={selectedPersonaId}
            />

            {/* Natural Query Input */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800 uppercase tracking-wide flex items-center gap-1.5">
                  <span>💬</span>
                  <span>
                    {isHi
                      ? 'अपनी आवश्यकता या परिस्थिति हिंदी या अंग्रेजी में लिखें'
                      : 'Ask Any Welfare Question (Vernacular or English)'}
                  </span>
                </label>
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  {isHi ? 'शून्य-भ्रांति गारंटी' : 'Zero-Hallucination'}
                </span>
              </div>

              <div className="relative">
                <textarea
                  value={agentQueryText}
                  onChange={(e) => setAgentQueryText(e.target.value)}
                  placeholder={
                    isHi
                      ? 'उदा. मैं अलवर की 68 वर्षीय विधवा हूँ, आय 40,000 है। मुझे कौनसी मासिक पेंशन मिलेगी और ई-मित्र पर क्या दस्तावेज लगेंगे?'
                      : 'e.g. I am a 68-year-old widow from Alwar earning 40,000. What monthly pension will I get and what circulars back this?'
                  }
                  rows={3}
                  className="w-full text-xs sm:text-sm p-3.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 focus:outline-hidden transition-all text-slate-800 resize-none font-sans"
                />
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
                <div className="flex flex-wrap gap-1.5">
                  <span className="text-[10px] font-semibold text-slate-400 self-center">
                    {isHi ? 'त्वरित प्रश्न:' : 'Suggested:'}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      const q = isHi
                        ? 'क्या मुझे 3 बीघा जमीन पर राजस्थान किसान सम्मान निधि की किस्त मिलेगी?'
                        : 'Am I eligible for Rajasthan Kisan Samman Nidhi on 3 bighas land?';
                      setAgentQueryText(q);
                    }}
                    className="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-700 px-2 py-1 rounded-md transition-colors cursor-pointer"
                  >
                    {isHi ? '🌾 3 बीघा किसान किस्त' : '🌾 3 Bigha Farmer DBT'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const q = isHi
                        ? '12वीं में 82% अंक हैं, काली बाई स्कूटी के लिए क्या नियम हैं?'
                        : '82% marks in 12th board, what are Kali Bai Scooty rules?';
                      setAgentQueryText(q);
                    }}
                    className="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-700 px-2 py-1 rounded-md transition-colors cursor-pointer"
                  >
                    {isHi ? '🎓 82% छात्रा स्कूटी' : '🎓 Girl Student Scooty'}
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => handleRunAgent()}
                  disabled={isAgentRunning || !agentQueryText.trim()}
                  className="py-2.5 px-6 bg-orange-600 hover:bg-orange-700 active:bg-orange-800 disabled:opacity-50 text-white font-extrabold text-xs sm:text-sm rounded-xl shadow-md hover:shadow transition-all flex items-center justify-center gap-2 cursor-pointer self-end sm:self-auto"
                >
                  {isAgentRunning ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>{isHi ? 'एजेंट सोच रहा है…' : 'Agent Reasoning…'}</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>{isHi ? 'एजेंट द्वारा जांचें' : 'Execute ReAct Agent'}</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Agent Running Indicator */}
            {isAgentRunning && (
              <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-xl border border-slate-800 space-y-4 animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                  <div>
                    <h4 className="text-sm font-bold text-emerald-400">
                      {isHi
                        ? 'बहु-चरणीय ReAct एजेंट सक्रिय: विचार → उपकरण चयन → अवलोकन'
                        : 'ReAct Agent Active: Thought → Tool Dispatch → Observation'}
                    </h4>
                    <p className="text-xs text-slate-400">
                      {isHi
                        ? 'शून्य-भ्रांति नियम ट्री और राजपत्रित परिपत्रों से प्रामाणिक मिलान जारी है…'
                        : 'Validating against deterministic AST rules & gazetted circular chunks…'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Agent Results Display */}
            {agentResponse && !isAgentRunning && (
              <div className="space-y-6">
                {/* Final Vernacular Answer Card */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-md overflow-hidden">
                  <div className="bg-linear-to-r from-orange-600 to-amber-600 text-white p-4 sm:p-5 flex items-start justify-between gap-3">
                    <div>
                      <div className="inline-flex items-center gap-1 text-[11px] font-bold bg-white/20 px-2 py-0.5 rounded-full mb-1">
                        <span>🎯</span>
                        <span>{isHi ? 'सत्यापित परामर्श निष्कर्ष' : 'Verified Welfare Recommendation'}</span>
                      </div>
                      <h3 className="text-base sm:text-lg font-black leading-snug">
                        {isHi ? 'आपकी पात्रता एवं वित्तीय लाभ विवरण' : 'Citizen Eligibility & Payout Summary'}
                      </h3>
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsEmitraSlipOpen(true)}
                      className="px-3 py-1.5 bg-white text-orange-800 hover:bg-orange-50 font-bold text-xs rounded-xl shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer shrink-0"
                    >
                      <span>🖨️</span>
                      <span>{isHi ? 'ई-मित्र पर्ची प्रिंट' : 'Print e-Mitra Slip'}</span>
                    </button>
                  </div>

                  <div className="p-5 sm:p-6 text-slate-800 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-sans">
                    {agentResponse.final_answer}
                  </div>
                </div>

                {/* Agent Reasoning Trace Accordion */}
                <AgentReasoningTrace
                  language={language}
                  steps={agentResponse.steps}
                  executionTimeMs={agentResponse.execution_time_ms}
                  citations={agentResponse.structured_data.citations}
                  onCitationClick={(cit) => setSelectedCitation(cit)}
                />

                {/* Recommended Schemes Grid */}
                {agentResponse.structured_data.recommended_schemes &&
                  agentResponse.structured_data.recommended_schemes.length > 0 && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
                          <span>📋</span>
                          <span>{isHi ? 'पात्र सरकारी योजनाएं' : 'Eligible Flagship Schemes'}</span>
                        </h4>
                        <span className="text-xs font-bold text-orange-700 bg-orange-50 px-2 py-0.5 rounded">
                          {agentResponse.structured_data.recommended_schemes.length} {isHi ? 'योजनाएं' : 'Schemes'}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {agentResponse.structured_data.recommended_schemes.map((s, idx) => (
                          <div
                            key={idx}
                            className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-orange-300 transition-colors flex flex-col justify-between"
                          >
                            <div>
                              <div className="flex items-start justify-between gap-2 mb-1">
                                <span className="text-xs font-extrabold text-slate-900 leading-snug">
                                  {isHi ? s.name_hi || s.name_en : s.name_en}
                                </span>
                                <span className="text-[10px] font-mono text-slate-400">
                                  {s.scheme_code}
                                </span>
                              </div>
                              <div className="text-xs font-black text-emerald-700 mt-1">
                                {typeof s.benefit_summary === 'object' && s.benefit_summary !== null
                                  ? ((s.benefit_summary as any).monthly_payout_inr
                                      ? `₹${(s.benefit_summary as any).monthly_payout_inr}/माह (${(s.benefit_summary as any).slab_applied || 'डीबीटी'})`
                                      : (s.benefit_summary as any).slab_applied || (isHi ? 'डीबीटी वित्तीय सहायता' : 'Direct DBT Financial Benefit'))
                                  : (s.benefit_summary || (isHi ? 'डीबीटी वित्तीय सहायता' : 'Direct DBT Financial Benefit'))}
                              </div>
                            </div>

                            <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between">
                              <span className="text-[10px] font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                {isHi ? 'पात्र (Eligible)' : 'Eligible'}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleViewDetails(s.scheme_code)}
                                className="text-xs font-bold text-orange-700 hover:text-orange-800 cursor-pointer"
                              >
                                {isHi ? 'विस्तार से देखें →' : 'Full Rules →'}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Mandatory Documents Checklist */}
                {agentResponse.structured_data.required_documents &&
                  agentResponse.structured_data.required_documents.length > 0 && (
                    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                          <span>📑</span>
                          <span>
                            {isHi
                              ? 'ई-मित्र पर ले जाने हेतु आवश्यक मूल दस्तावेज'
                              : 'Mandatory Documents Checklist for Kiosk'}
                          </span>
                        </h4>
                        <span className="text-[10px] font-semibold text-slate-500">
                          {isHi ? 'आवेदन से पूर्व तैयार रखें' : 'Keep ready before visit'}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {agentResponse.structured_data.required_documents.map((doc, i) => (
                          <div
                            key={i}
                            className="flex items-start gap-2.5 p-2.5 bg-slate-50 rounded-xl border border-slate-200/80 text-xs"
                          >
                            <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 font-bold flex items-center justify-center shrink-0 mt-0.5">
                              ✓
                            </span>
                            <div>
                              <div className="font-bold text-slate-800">{doc.document_name}</div>
                              <div className="text-[11px] text-slate-500">{doc.purpose}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Kiosk & Support Information */}
                {agentResponse.structured_data.emitra_kiosk_info && (
                  <div className="bg-linear-to-br from-amber-500/10 to-orange-500/10 border border-amber-300/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">🏢</span>
                        <h4 className="text-xs font-extrabold text-amber-950 uppercase tracking-wide">
                          {isHi ? 'निकटतम ई-मित्र सहायता केंद्र' : 'Nearest e-Mitra Kiosks & Helpline'}
                        </h4>
                      </div>
                      <p className="text-xs text-amber-900">
                        {agentResponse.structured_data.emitra_kiosk_info.citizen_tip}
                      </p>
                      <div className="text-xs font-mono font-bold text-amber-800 pt-1">
                        राजस्थान संपर्क हेल्पलाइन: 181 (टोल-फ्री) • ई-मित्र सपोर्ट: 0141-2221424
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsEmitraSlipOpen(true)}
                      className="py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors shrink-0 flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>🖨️</span>
                      <span>{isHi ? 'टोकन पर्ची प्रिंट करें' : 'Print Kiosk Slip'}</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* MODE 2: LIVE SIMULATOR (Interactive Sliders & Dynamic Payout) */}
        {/* ------------------------------------------------------------- */}
        {activeMode === 'SIMULATOR' && (
          <EligibilitySimulator
            language={language}
            onApplyToAgent={handleApplySimulatorToAgent}
          />
        )}

        {/* ------------------------------------------------------------- */}
        {/* MODE 3: GUIDED QUESTIONNAIRE (Step-by-Step Interview)         */}
        {/* ------------------------------------------------------------- */}
        {activeMode === 'GUIDED' && (
          <div className="space-y-6">
            {/* Informational Query Answer Banner */}
            {infoBanner && (
              <div
                role="status"
                className="p-4 bg-blue-50 border border-blue-200 text-blue-900 rounded-2xl text-sm flex items-start justify-between gap-3 shadow-xs"
              >
                <div className="flex gap-2.5 items-start">
                  <span className="text-lg">💡</span>
                  <p className="font-medium leading-relaxed">
                    {isHi ? infoBanner.text_hi : infoBanner.text_en}
                  </p>
                </div>
                <button
                  onClick={() => setInfoBanner(null)}
                  className="text-blue-500 hover:text-blue-700 font-bold cursor-pointer"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Profile facts summary */}
            {sessionId && Object.keys(citizenProfile).length > 0 && (
              <ProfileSummary
                profile={citizenProfile}
                language={language}
                onEditFact={() => {}}
              />
            )}

            {/* START STATE: Initial Need Input */}
            {flowState === 'START' && (
              <NeedInput
                onSubmit={handleSubmitNeed}
                language={language}
                isLoading={isProcessing}
              />
            )}

            {/* CONFIRMATION CARD */}
            {flowState === 'CONFIRMATION' && currentConversation && (
              <ConfirmationCard
                message={currentConversation.message}
                expectedInput={currentConversation.expected_input}
                lang={language}
                isSubmitting={isProcessing}
                onConfirmYes={() => {}}
                onConfirmNo={() => {}}
                onSendTextAnswer={() => {}}
              />
            )}

            {/* CLARIFICATION CARD */}
            {flowState === 'CLARIFICATION' && currentConversation && (
              <ClarificationCard
                message={currentConversation.message}
                expectedInput={currentConversation.expected_input}
                lang={language}
                isSubmitting={isProcessing}
                onSubmitText={() => {}}
                onSkipField={() => {}}
              />
            )}

            {/* QUESTION CARD */}
            {flowState === 'COLLECTING_INFORMATION' && nextQuestion && (
              <QuestionCard
                question={nextQuestion}
                language={language}
                onSubmitAnswer={() => {}}
                onDecline={() => {}}
                isSubmitting={isProcessing}
              />
            )}

            {/* RESULTS LIST */}
            {flowState === 'RESULTS' && (
              <ResultsList
                eligibleSchemes={eligibleSchemes}
                moreInfoSchemes={moreInfoSchemes}
                language={language}
                onSelectScheme={handleViewDetails}
                onResetNeed={handleStartOver}
              />
            )}
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* MODE 4: VOICE ASSISTANT (Bilingual Voice Assistant)           */}
        {/* ------------------------------------------------------------- */}
        {activeMode === 'VOICE' && (
          sessionId ? (
            <VoiceMode
              sessionId={sessionId}
              conversationVersion={currentConversation?.meta?.version}
              currentConversation={currentConversation}
              lang={language}
              onConversationResponse={applyConversationResponse}
              onSwitchToText={() => setActiveMode('AGENT')}
              onStartOver={handleStartOver}
            />
          ) : (
            <div className="w-full bg-white dark:bg-slate-900 rounded-3xl p-12 border border-slate-200 dark:border-slate-800 text-center space-y-4 shadow-sm">
              <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                {isHi ? 'आवाज़ सत्र प्रारंभ हो रहा है…' : 'Initializing voice session…'}
              </p>
            </div>
          )
        )}

        {/* MODAL 1: CITATION DRAWER (Official Gazette Evidence) */}
        {selectedCitation && (
          <CitationDrawer
            language={language}
            citation={selectedCitation}
            onClose={() => setSelectedCitation(null)}
          />
        )}

        {/* MODAL 2: E-MITRA APPLICATION SLIP */}
        <EmitraSlipModal
          language={language}
          isOpen={isEmitraSlipOpen}
          onClose={() => setIsEmitraSlipOpen(false)}
          citizenName={
            selectedPersonaId
              ? PRESET_PERSONAS.find((p) => p.id === selectedPersonaId)?.[isHi ? 'name_hi' : 'name_en']
              : isHi
              ? 'नागरिक'
              : 'Citizen'
          }
          district={agentContext?.district || 'Rajasthan'}
          age={agentContext?.age}
          gender={agentContext?.gender}
          schemes={agentResponse?.structured_data.recommended_schemes || []}
          documents={agentResponse?.structured_data.required_documents || []}
          kioskInfo={agentResponse?.structured_data.emitra_kiosk_info}
        />

        {/* MODAL 3: SCHEME DETAILS */}
        {selectedSchemeId && (
          <div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
          >
            <div className="bg-white rounded-3xl max-w-3xl w-full max-h-[92vh] overflow-y-auto shadow-2xl p-6 sm:p-8 relative my-auto">
              <button
                onClick={handleCloseDetail}
                aria-label={isHi ? 'बंद करें' : 'Close'}
                className="absolute top-5 right-5 w-9 h-9 flex items-center justify-center text-slate-400 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-full transition cursor-pointer"
              >
                ✕
              </button>

              {loadingDetail && (
                <div className="py-16 text-center space-y-3">
                  <div className="w-10 h-10 border-3 border-orange-600 border-t-transparent rounded-full animate-spin mx-auto" />
                  <p className="text-sm font-medium text-slate-600">
                    {isHi ? 'योजना की जानकारी लोड हो रही है…' : 'Loading verified scheme details…'}
                  </p>
                </div>
              )}

              {detailError && (
                <div className="py-12 text-center space-y-3">
                  <p className="text-rose-600 font-medium">{detailError}</p>
                  <button
                    onClick={handleCloseDetail}
                    className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl text-sm font-semibold cursor-pointer"
                  >
                    {isHi ? 'वापस जाएँ' : 'Go Back'}
                  </button>
                </div>
              )}

              {schemeDetail && !loadingDetail && (
                <SchemeDetails
                  scheme={schemeDetail}
                  language={language}
                  onBack={handleCloseDetail}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </CitizenShell>
  );
}
