'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { VoiceTransportState, VoiceTurnResponse } from '@/types/voice';
import { CitizenSchemeCard, ConversationTurnResponse } from '@/types/citizen';
import {
  sendVoiceTurn,
  getVoiceResponseAudioUrl,
  replayVoiceResponse,
} from '@/lib/api';
import { config } from '@/lib/config';
import { useVoiceRecorder } from './useVoiceRecorder';
import { VoiceStatus } from './VoiceStatus';
import { AudioWaveform } from './AudioWaveform';
import { cleanTextForSpeech, findBestVoice } from '@/lib/speechHelpers';
import {
  DialogueProfile,
  processDialogueTurn,
  toCitizenSchemeCard,
} from '@/lib/voiceConversationEngine';
import { RAJASTHAN_FLAGSHIP_SCHEMES } from '@/lib/rajasthanSchemesData';

interface VoiceModeProps {
  sessionId: string;
  conversationVersion?: number;
  currentConversation?: ConversationTurnResponse | null;
  lang?: 'hi' | 'en';
  onConversationResponse: (response: ConversationTurnResponse) => void;
  onSwitchToText: () => void;
  onStartOver?: () => void;
  onEndConversation?: () => void;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  schemes?: CitizenSchemeCard[];
}

function playChime(type: 'start' | 'stop') {
  if (typeof window === 'undefined') return;
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    const now = ctx.currentTime;

    if (type === 'start') {
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
    } else {
      osc.frequency.setValueAtTime(750, now);
      osc.frequency.exponentialRampToValueAtTime(370, now + 0.12);
    }

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.15);
  } catch {}
}

export function VoiceMode({
  sessionId,
  conversationVersion,
  currentConversation,
  lang = 'hi',
  onConversationResponse,
  onSwitchToText,
  onStartOver,
  onEndConversation,
}: VoiceModeProps) {
  const isHi = lang === 'hi';
  const [transportState, setTransportState] = useState<VoiceTransportState>('READY');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [typedInput, setTypedInput] = useState<string>('');

  // Multi-Turn Conversational Memory
  const [dialogueProfile, setDialogueProfile] = useState<DialogueProfile>({});
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSchemes, setActiveSchemes] = useState<CitizenSchemeCard[]>([]);

  // Dynamic Suggestion Chips
  const [suggestedChips, setSuggestedChips] = useState<Array<{ label: string; text: string }>>([
    { label: isHi ? '👴 65+ वृद्धजन पेंशन' : 'Senior Pension', text: isHi ? 'मेरी उम्र 65 वर्ष है, मुझे वृद्धजन पेंशन योजना की जानकारी चाहिए।' : 'I am 65 years old. What senior pension schemes am I eligible for?' },
    { label: isHi ? '🌾 3 बीघा ज़मीन, किसान सहायता' : 'Farmer Support', text: isHi ? 'मेरे पास 3 बीघा कृषि भूमि है, मुझे किसान सम्मान निधि सहायता चाहिए।' : 'I have 3 bighas of land. What farmer benefits can I receive?' },
    { label: isHi ? '👩 एकल नारी (विधवा) पेंशन' : 'Widow Pension', text: isHi ? 'मैं विधवा महिला हूँ, मुझे एकल नारी पेंशन योजना का लाभ चाहिए।' : 'I am a widow in Rajasthan. How can I apply for Ekal Nari pension?' },
    { label: isHi ? '🎓 छात्र निःशुल्क कोचिंग' : 'Free Coaching', text: isHi ? 'मैं 12वीं पास छात्र हूँ, अनुप्रति कोचिंग योजना की पात्रता क्या है?' : 'What are the eligibility criteria for Anuprati Free Coaching Scheme?' },
    { label: isHi ? '🏥 ₹25 लाख मुफ्त स्वास्थ्य उपचार' : 'Free Healthcare', text: isHi ? 'आयुष्मान आरोग्य योजना में ₹25 लाख कैशलेस इलाज कैसे मिलेगा?' : 'How does the 25 lakh cashless healthcare coverage work?' },
  ]);

  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const audioBlobUrlRef = useRef<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Initialize initial welcome message
  useEffect(() => {
    if (messages.length === 0) {
      const welcomeText = isHi
        ? 'नमस्ते! मैं योजनसेतु आवाज़ सहायक हूँ। राजस्थान की 9 प्रमुख जनकल्याणकारी योजनाओं की पात्रता जानने के लिए अपनी उम्र, पेशा, या आवश्यकता बोलकर बताइए।'
        : 'Hello! I am YojanSetu Voice Assistant. Speak about your age, occupation, or welfare needs to find eligible Rajasthan government schemes.';

      setMessages([
        {
          id: 'msg_welcome',
          sender: 'assistant',
          text: welcomeText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [isHi, messages.length]);

  // Scroll to bottom of dialogue on new message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, transportState]);

  // Resolves backend relative or absolute audio URLs to full fetchable backend URLs
  const resolveAudioUrl = useCallback(
    (rawUrl?: string, responseId?: string): string => {
      if (sessionId && responseId && !responseId.startsWith('local_')) {
        return getVoiceResponseAudioUrl(sessionId, responseId);
      }
      if (!rawUrl) return '';
      if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://') || rawUrl.startsWith('blob:')) {
        return rawUrl;
      }
      const baseUrl = config.apiBaseUrl.replace(/\/+$/, '');
      if (rawUrl.startsWith('/api/v1/')) {
        return `${baseUrl}${rawUrl.slice('/api/v1'.length)}`;
      }
      if (rawUrl.startsWith('/')) {
        return `${baseUrl}${rawUrl}`;
      }
      return `${baseUrl}/${rawUrl}`;
    },
    [sessionId]
  );

  // Stop audio playback cleanly
  const stopPlayback = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      audioPlayerRef.current = null;
    }
    if (audioBlobUrlRef.current) {
      URL.revokeObjectURL(audioBlobUrlRef.current);
      audioBlobUrlRef.current = null;
    }
    setIsPlaying(false);
    setTransportState('READY');
  }, []);

  // Web Speech Synthesis browser fallback with natural voice selection & clean text
  const speakBrowserSynthesis = useCallback(
    (rawText: string) => {
      stopPlayback();
      if (typeof window === 'undefined' || !window.speechSynthesis) {
        setTransportState('READY');
        return;
      }

      const spokenText = cleanTextForSpeech(rawText, lang);
      if (!spokenText.trim()) {
        setTransportState('READY');
        return;
      }

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(spokenText);
      utterance.lang = isHi ? 'hi-IN' : 'en-IN';
      utterance.rate = 0.95;
      utterance.pitch = 1.0;

      const bestVoice = findBestVoice(lang);
      if (bestVoice) {
        utterance.voice = bestVoice;
      }

      setIsPlaying(true);
      setTransportState('SPEAKING');

      utterance.onend = () => {
        setIsPlaying(false);
        setTransportState('READY');
      };

      utterance.onerror = () => {
        setIsPlaying(false);
        setTransportState('READY');
      };

      window.speechSynthesis.speak(utterance);
    },
    [isHi, lang, stopPlayback]
  );

  // Play synthesized audio stream enforcing half-duplex rules
  const playAudioStream = useCallback(
    (audioUrl: string, fallbackText?: string) => {
      stopPlayback();

      if (!audioUrl) {
        if (fallbackText) {
          speakBrowserSynthesis(fallbackText);
        } else {
          setTransportState('READY');
        }
        return;
      }

      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;
      setIsPlaying(true);
      setTransportState('SPEAKING');

      audio.onended = () => {
        stopPlayback();
      };

      audio.onerror = () => {
        stopPlayback();
        if (fallbackText) {
          speakBrowserSynthesis(fallbackText);
        }
      };

      audio.play().catch(() => {
        stopPlayback();
        if (fallbackText) {
          speakBrowserSynthesis(fallbackText);
        }
      });
    },
    [stopPlayback, speakBrowserSynthesis]
  );

  // Core Dialogue Handler: Processes Citizen Turn & Executes Reasoning
  const handleTurnSubmission = useCallback(
    async (text: string, audioBlob?: Blob) => {
      const cleanInput = text.trim();
      if (!cleanInput) return;

      playChime('stop');
      setTransportState('PROCESSING_AUDIO');
      setErrorMessage(null);

      // Add user utterance to dialogue history
      const userMessage: ChatMessage = {
        id: `user_${Date.now()}`,
        sender: 'user',
        text: cleanInput,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, userMessage]);

      const blobToSend = audioBlob || new Blob([new Uint8Array(44)], { type: 'audio/wav' });
      const voiceTurnId = `vturn_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      try {
        setTransportState('TRANSCRIBING');

        // Execute conversational reasoning with authentic schemes
        const turnResult = await sendVoiceTurn(
          sessionId,
          blobToSend,
          voiceTurnId,
          conversationVersion,
          cleanInput,
          lang,
          dialogueProfile
        );

        // Update accumulated profile facts locally
        const dialogueRun = processDialogueTurn(cleanInput, dialogueProfile, lang);
        setDialogueProfile(dialogueRun.updatedProfile);

        // Update dynamic suggestion chips for the next turn
        if (dialogueRun.suggestedChips && dialogueRun.suggestedChips.length > 0) {
          setSuggestedChips(
            dialogueRun.suggestedChips.map((c) => ({
              label: isHi ? c.label_hi : c.label_en,
              text: c.text,
            }))
          );
        }

        const eligibleCards = turnResult.conversation?.results?.eligible || [];
        if (eligibleCards.length > 0) {
          setActiveSchemes(eligibleCards);
        }

        // Add assistant reply to dialogue thread
        const replyText = isHi
          ? turnResult.conversation?.message?.text_hi || dialogueRun.displayReply
          : turnResult.conversation?.message?.text_en || dialogueRun.displayReply;

        const assistantMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          sender: 'assistant',
          text: replyText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          schemes: eligibleCards.length > 0 ? eligibleCards : undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Forward to parent page
        if (turnResult.conversation) {
          onConversationResponse(turnResult.conversation);
        }

        // Vocal audio playback: prefer clean spoken text
        const speechToSay = dialogueRun.spokenReply || replyText;
        if (turnResult.audio?.audio_url) {
          const streamUrl = resolveAudioUrl(turnResult.audio.audio_url, turnResult.audio.response_id);
          playAudioStream(streamUrl, speechToSay);
        } else {
          speakBrowserSynthesis(speechToSay);
        }
      } catch (err: any) {
        console.error('Dialogue turn error:', err);
        setTransportState('READY');
        setErrorMessage(
          err.message ||
            (isHi
              ? 'बातचीत प्रोसेस करने में त्रुटि हुई। कृपया दोबारा बोलें।'
              : 'Error processing dialogue. Please speak again.')
        );
      }
    },
    [
      sessionId,
      conversationVersion,
      lang,
      dialogueProfile,
      isHi,
      onConversationResponse,
      playAudioStream,
      resolveAudioUrl,
      speakBrowserSynthesis,
    ]
  );

  // Recorder Callback
  const handleRecordingComplete = useCallback(
    (audioBlob: Blob, liveTranscript?: string) => {
      const text = (liveTranscript || '').trim();
      handleTurnSubmission(text, audioBlob);
    },
    [handleTurnSubmission]
  );

  // MediaRecorder Hook
  const {
    isRecording,
    permissionState,
    recordingDuration,
    audioLevel,
    liveTranscript,
    startRecording: triggerStartRecording,
    stopRecording,
  } = useVoiceRecorder({
    maxDurationSeconds: 60,
    silenceTimeoutSeconds: 2.2,
    autoStopOnSilence: true,
    lang,
    onRecordingComplete: handleRecordingComplete,
    onError: (err) => {
      setTransportState('READY');
      setErrorMessage(
        err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError'
          ? (isHi ? 'माइक्रोफ़ोन अनुमति नहीं मिली। आप नीचे टाइप कर सकते हैं।' : 'Microphone access denied. You can type below.')
          : err.message
      );
    },
  });

  const startRecordingSafe = useCallback(() => {
    if (isPlaying) {
      stopPlayback();
    }
    playChime('start');
    setTransportState('LISTENING');
    triggerStartRecording();
  }, [isPlaying, stopPlayback, triggerStartRecording]);

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedInput.trim() || isRecording || transportState === 'PROCESSING_AUDIO') return;
    const text = typedInput.trim();
    setTypedInput('');
    handleTurnSubmission(text);
  };

  const handleReplayLast = useCallback(() => {
    const lastAsst = [...messages].reverse().find((m) => m.sender === 'assistant');
    if (lastAsst) {
      speakBrowserSynthesis(lastAsst.text);
    }
  }, [messages, speakBrowserSynthesis]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, [stopPlayback]);

  const isProcessing =
    transportState === 'PROCESSING_AUDIO' ||
    transportState === 'TRANSCRIBING' ||
    transportState === 'PROCESSING_TURN' ||
    transportState === 'SYNTHESIZING';

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col bg-white dark:bg-slate-900 rounded-3xl border border-slate-200/90 dark:border-slate-800 shadow-xl overflow-hidden mb-8 transition-all">
      {/* Sleek Minimal Header */}
      <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800/80 flex items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-900/50 backdrop-blur-xs">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white flex items-center justify-center font-bold text-lg shadow-md shadow-indigo-500/20">
            🎙️
          </div>
          <div>
            <h3 className="font-extrabold text-slate-900 dark:text-slate-100 text-base leading-tight">
              {isHi ? 'योजनसेतु आवाज़ सहायक' : 'YojanSetu Voice Assistant'}
            </h3>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
              {isHi ? 'सत्यापित सरकारी नियम एवं बहु-चरणीय संवाद' : 'Verified Rajasthan Rules & Dialogue'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <VoiceStatus
            state={transportState}
            lang={lang}
            recordingDuration={recordingDuration}
          />
          {onStartOver && (
            <button
              type="button"
              onClick={() => {
                setDialogueProfile({});
                setMessages([]);
                setActiveSchemes([]);
                onStartOver();
              }}
              title={isHi ? 'नया सत्र शुरू करें' : 'Start new session'}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer text-xs"
            >
              🔄
            </button>
          )}
        </div>
      </div>

      {/* Central Interactive Voice Orb Section */}
      <div className="py-6 px-4 bg-gradient-to-b from-indigo-50/40 via-transparent to-transparent dark:from-indigo-950/20 flex flex-col items-center justify-center relative">
        {/* Pulsating Voice Orb / Avatar */}
        <div className="relative flex items-center justify-center mb-2">
          {/* Animated Halo Rings */}
          <div
            className={`w-28 h-28 sm:w-32 sm:h-32 rounded-full absolute transition-all duration-300 ${
              isRecording
                ? 'bg-rose-500/20 dark:bg-rose-500/30 scale-125 animate-ping'
                : isPlaying
                ? 'bg-emerald-500/20 dark:bg-emerald-500/30 scale-115 animate-pulse'
                : isProcessing
                ? 'bg-amber-500/20 dark:bg-amber-500/30 scale-110 animate-spin'
                : 'bg-indigo-500/10 dark:bg-indigo-500/20 scale-100'
            }`}
          />

          {/* Main Action Button in Orb */}
          <button
            type="button"
            onClick={
              isPlaying
                ? stopPlayback
                : isRecording
                ? stopRecording
                : startRecordingSafe
            }
            disabled={isProcessing}
            aria-label={
              isPlaying
                ? isHi ? 'आवाज़ रोकें' : 'Stop voice'
                : isRecording
                ? isHi ? 'भेजें' : 'Send voice'
                : isHi ? 'बोलने के लिए दबाएँ' : 'Tap to speak'
            }
            className={`w-20 h-20 sm:w-24 sm:h-24 rounded-full flex flex-col items-center justify-center text-white font-bold shadow-2xl transition-all duration-200 relative z-10 cursor-pointer ${
              isPlaying
                ? 'bg-gradient-to-tr from-amber-500 to-orange-500 shadow-amber-500/30 hover:scale-105 active:scale-95 ring-4 ring-amber-200 dark:ring-amber-900/50'
                : isRecording
                ? 'bg-gradient-to-tr from-rose-600 to-red-600 shadow-rose-600/40 hover:scale-105 active:scale-95 ring-4 ring-rose-200 dark:ring-rose-900/50 animate-pulse'
                : isProcessing
                ? 'bg-slate-400 cursor-not-allowed shadow-none'
                : 'bg-gradient-to-tr from-indigo-600 via-indigo-700 to-violet-700 shadow-indigo-600/40 hover:scale-105 active:scale-95 ring-4 ring-indigo-200 dark:ring-indigo-900/60'
            }`}
          >
            {isPlaying ? (
              <>
                <span className="text-2xl">⏹️</span>
                <span className="text-[10px] mt-0.5 font-bold uppercase tracking-wider">{isHi ? 'रोकें' : 'Stop'}</span>
              </>
            ) : isRecording ? (
              <>
                <span className="text-2xl">⏹️</span>
                <span className="text-[10px] mt-0.5 font-bold uppercase tracking-wider">{isHi ? 'भेजें' : 'Send'}</span>
              </>
            ) : isProcessing ? (
              <span className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span className="text-2xl animate-bounce">🎙️</span>
                <span className="text-[10px] mt-0.5 font-bold uppercase tracking-wider">{isHi ? 'बोलें' : 'Speak'}</span>
              </>
            )}
          </button>
        </div>

        {/* Real-time Frequency Waveform */}
        <div className="w-full max-w-xs -mt-1">
          <AudioWaveform
            isRecording={isRecording}
            isPlaying={isPlaying}
            audioLevel={audioLevel}
            lang={lang}
          />
        </div>

        {/* Live speech transcription bubble */}
        {isRecording && (
          <div className="mt-2 px-4 py-2 rounded-full bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs font-medium animate-pulse flex items-center gap-2 max-w-md text-center">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping shrink-0" />
            <span className="truncate">
              {liveTranscript ? `“${liveTranscript}”` : isHi ? 'आपकी बात सुन रहा हूँ, बोलिए…' : 'Listening, speak now…'}
            </span>
          </div>
        )}
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="mx-6 mb-4 p-3 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
          <span>⚠️ {errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-400 hover:text-rose-700 font-bold ml-2">✕</button>
        </div>
      )}

      {/* Conversational Chat Dialogue Stream */}
      <div className="flex-1 max-h-[380px] overflow-y-auto px-6 py-4 space-y-4 border-t border-b border-slate-100 dark:border-slate-800/80 bg-slate-50/30 dark:bg-slate-900/30">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Message Bubble */}
            <div
              className={`max-w-[85%] sm:max-w-[78%] rounded-2xl p-4 text-xs sm:text-sm leading-relaxed shadow-xs ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-xs'
                  : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-200/80 dark:border-slate-700/80 rounded-bl-xs'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5 opacity-75 text-[10px] font-semibold">
                <span>{msg.sender === 'user' ? (isHi ? 'आप' : 'You') : '🏛️ YojanSetu'}</span>
                <span>{msg.timestamp}</span>
              </div>

              <div className="whitespace-pre-wrap font-sans">
                {msg.text}
              </div>

              {/* Speaker Replay Icon on Assistant message */}
              {msg.sender === 'assistant' && (
                <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-700/50 flex items-center justify-end">
                  <button
                    type="button"
                    onClick={() => speakBrowserSynthesis(msg.text)}
                    disabled={isPlaying || isRecording}
                    className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer disabled:opacity-40"
                  >
                    <span>🔊</span>
                    <span>{isHi ? 'दोबारा सुनें' : 'Listen'}</span>
                  </button>
                </div>
              )}
            </div>

            {/* If schemes attached to assistant message, render compact showcase pills */}
            {msg.schemes && msg.schemes.length > 0 && (
              <div className="w-full max-w-xl mt-3 space-y-2.5">
                <div className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <span>✨</span>
                  <span>{isHi ? `पात्र योजनाएँ (${msg.schemes.length}):` : `Eligible Schemes (${msg.schemes.length}):`}</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {msg.schemes.map((scheme, sIdx) => (
                    <div
                      key={sIdx}
                      className="p-3.5 rounded-2xl bg-white dark:bg-slate-800/90 border border-emerald-300 dark:border-emerald-800 shadow-xs hover:border-emerald-400 transition-colors flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="text-xs font-extrabold text-slate-900 dark:text-slate-100 leading-snug line-clamp-1">
                            {isHi ? scheme.name_hi || scheme.name_en : scheme.name_en}
                          </span>
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 shrink-0">
                            पात्र
                          </span>
                        </div>
                        <p className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 mb-1">
                          💰 {isHi ? scheme.primary_benefit_hi : scheme.primary_benefit_en}
                        </p>
                        <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-2">
                          {isHi ? scheme.purpose_hi : scheme.purpose_en}
                        </p>
                      </div>

                      <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 font-mono">{scheme.scheme_code}</span>
                        <button
                          type="button"
                          onClick={onSwitchToText}
                          className="font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                        >
                          {isHi ? 'विस्तृत पर्ची ➔' : 'View Slip ➔'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Dynamic Conversational Suggestion Chips */}
      {!isRecording && !isProcessing && (
        <div className="px-6 py-3 bg-slate-50/70 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider shrink-0">
            {isHi ? 'त्वरित उत्तर:' : 'Quick Reply:'}
          </span>
          <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto">
            {suggestedChips.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleTurnSubmission(chip.text)}
                className="px-3 py-1.5 rounded-full bg-white dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-indigo-600 text-xs font-semibold shadow-2xs transition-all hover:scale-102 active:scale-98 cursor-pointer"
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Bottom Minimal Input Bar */}
      <div className="px-6 py-4 bg-white dark:bg-slate-900 flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Quick In-Voice Text Input Form */}
        <form onSubmit={handleManualSubmit} className="w-full sm:flex-1 flex items-center gap-2">
          <input
            type="text"
            value={typedInput}
            onChange={(e) => setTypedInput(e.target.value)}
            disabled={isProcessing || isRecording}
            placeholder={
              isHi
                ? 'माइक के अलावा यहाँ लिखकर भी पूछ सकते हैं (उदा: मेरी उम्र 65 साल है)…'
                : 'Or type here (e.g. I am 65 years old farmer)...'
            }
            className="flex-1 px-4 py-2 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 transition-all"
          />
          <button
            type="submit"
            disabled={!typedInput.trim() || isProcessing}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs sm:text-sm shadow-xs transition-colors disabled:opacity-40 cursor-pointer"
          >
            {isHi ? 'भेजें' : 'Send'}
          </button>
        </form>

        {/* Action Controls */}
        <div className="flex items-center gap-2 w-full sm:w-auto justify-end text-xs">
          <button
            type="button"
            onClick={handleReplayLast}
            disabled={isPlaying || isRecording || messages.length <= 1}
            className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5"
            title={isHi ? 'पिछला उत्तर दोबारा सुनें' : 'Listen last response again'}
          >
            <span>🔊</span>
            <span>{isHi ? 'दोबारा सुनें' : 'Replay'}</span>
          </button>

          <button
            type="button"
            onClick={onSwitchToText}
            className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>📋</span>
            <span>{isHi ? 'पूरी योजना सूची' : 'Full List'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
