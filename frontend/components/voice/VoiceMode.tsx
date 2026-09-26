'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { VoiceTransportState, VoiceTurnResponse } from '@/types/voice';
import { ConversationTurnResponse } from '@/types/citizen';
import {
  sendVoiceTurn,
  getVoiceResponseAudioUrl,
  replayVoiceResponse,
} from '@/lib/api';
import { config } from '@/lib/config';
import { useVoiceRecorder } from './useVoiceRecorder';
import { VoiceStatus } from './VoiceStatus';
import { VoiceControls } from './VoiceControls';
import { AudioWaveform } from './AudioWaveform';
import { cleanTextForSpeech, findBestVoice } from '@/lib/speechHelpers';

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

// Gentle pleasant Web Audio chime for microphone start/stop
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
  const [lastTranscript, setLastTranscript] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [hasUserInteracted, setHasUserInteracted] = useState<boolean>(false);

  const [activeConversation, setActiveConversation] = useState<ConversationTurnResponse | null>(
    currentConversation || null
  );

  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const audioBlobUrlRef = useRef<string | null>(null);

  // Sync prop changes into state
  useEffect(() => {
    if (currentConversation) {
      setActiveConversation(currentConversation);
    }
  }, [currentConversation]);

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
      utterance.rate = 0.95; // Crisp cadence
      utterance.pitch = 1.0;

      // Assign highest quality available voice
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

      utterance.onerror = (e) => {
        console.warn('SpeechSynthesis event notice:', e);
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

      audio.onerror = (err) => {
        console.warn('Audio stream error, falling back to speech synthesis:', err);
        stopPlayback();
        if (fallbackText) {
          speakBrowserSynthesis(fallbackText);
        } else {
          setFeedbackMessage(
            isHi
              ? 'ऑडियो प्लेबैक में समस्या आई। उत्तर नीचे स्क्रीन पर पढ़ सकते हैं।'
              : 'Audio playback encountered an issue. You can read the response on screen.'
          );
        }
      };

      audio.play().catch((playErr) => {
        console.warn('Browser prevented audio autoplay:', playErr);
        stopPlayback();
        if (fallbackText) {
          speakBrowserSynthesis(fallbackText);
        } else {
          setFeedbackMessage(
            isHi
              ? 'ब्राउज़र ने आवाज़ को स्वतः चलने से रोक दिया। सुनने के लिए "दोबारा सुनें" बटन दबाएँ।'
              : 'Browser blocked audio autoplay. Click "Replay" to listen.'
          );
        }
      });
    },
    [isHi, stopPlayback, speakBrowserSynthesis]
  );

  // Core Voice Turn Submission Handler
  const handleRecordingComplete = useCallback(
    async (audioBlob: Blob, liveTranscript?: string) => {
      playChime('stop');
      setTransportState('PROCESSING_AUDIO');
      setErrorMessage(null);
      setFeedbackMessage(null);
      setHasUserInteracted(true);

      const capturedText = (liveTranscript || '').trim();
      if (capturedText) {
        setLastTranscript(capturedText);
      }

      // Generate client-side turn UUID
      const voiceTurnId = `vturn_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      try {
        setTransportState('TRANSCRIBING');
        const turnResult: VoiceTurnResponse = await sendVoiceTurn(
          sessionId,
          audioBlob,
          voiceTurnId,
          activeConversation?.meta?.version ?? conversationVersion,
          capturedText,
          lang
        );

        // Update transcript if returned from backend STT
        if (turnResult.transcription?.text) {
          setLastTranscript(turnResult.transcription.text);
        }

        // Forward structured conversation response to parent page
        if (turnResult.conversation) {
          setActiveConversation(turnResult.conversation);
          onConversationResponse(turnResult.conversation);
        }

        // Handle retry warnings
        if (turnResult.warning) {
          setFeedbackMessage(turnResult.warning);
        }

        const replySpeech = isHi
          ? turnResult.conversation?.message?.text_hi
          : turnResult.conversation?.message?.text_en;

        // Play synthesized TTS audio if provided, or speak via browser SpeechSynthesis
        if (turnResult.audio?.audio_url) {
          const streamUrl = resolveAudioUrl(turnResult.audio.audio_url, turnResult.audio.response_id);
          playAudioStream(streamUrl, replySpeech);
        } else if (replySpeech) {
          speakBrowserSynthesis(replySpeech);
        } else {
          setTransportState('READY');
        }
      } catch (err: any) {
        console.error('Voice turn processing error:', err);
        setTransportState('READY');

        if (err.code === 'CONVERSATION_STATE_CONFLICT') {
          setErrorMessage(
            isHi
              ? 'बातचीत की स्थिति बदल गई है। कृपया उत्तर दोबारा दें।'
              : 'Conversation state changed. Please repeat your response.'
          );
        } else if (err.code === 'VOICE_TURN_ALREADY_ACTIVE') {
          setErrorMessage(
            isHi
              ? 'पिछला उत्तर अभी प्रोसेस हो रहा है। कृपया प्रतीक्षा करें।'
              : 'Previous turn is still processing. Please wait.'
          );
        } else {
          setErrorMessage(
            err.message ||
              (isHi
                ? 'आवाज़ प्रोसेस करने में त्रुटि हुई। कृपया दोबारा बोलें या नीचे टेक्स्ट में लिखें।'
                : 'Error processing voice. Please speak again or type in text below.')
          );
        }
      }
    },
    [
      sessionId,
      activeConversation,
      conversationVersion,
      isHi,
      lang,
      onConversationResponse,
      playAudioStream,
      resolveAudioUrl,
      speakBrowserSynthesis,
    ]
  );

  // Quick query handler (e.g. from suggestion chips or typed text bar)
  const handleQuickQuery = useCallback(
    (text: string) => {
      setLastTranscript(text);
      // Create lightweight dummy audio blob to accompany recognized text
      const dummyBlob = new Blob([new Uint8Array(44)], { type: 'audio/wav' });
      handleRecordingComplete(dummyBlob, text);
    },
    [handleRecordingComplete]
  );

  // MediaRecorder + Web Audio API level meter + SpeechRecognition hook
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
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage(
          isHi
            ? 'माइक्रोफ़ोन की अनुमति अस्वीकृत है। आप नीचे टेक्स्ट में लिखकर पूछ सकते हैं।'
            : 'Microphone permission denied. You can type below to ask questions.'
        );
      } else {
        setErrorMessage(err.message);
      }
    },
  });

  // Half-duplex guard: Prevent starting microphone while assistant is speaking
  const startRecordingSafe = useCallback(() => {
    if (isPlaying) {
      stopPlayback();
    }
    playChime('start');
    setTransportState('LISTENING');
    setHasUserInteracted(true);
    triggerStartRecording();
  }, [isPlaying, stopPlayback, triggerStartRecording]);

  // Replay last response
  const handleReplay = useCallback(async () => {
    if (isPlaying) {
      stopPlayback();
    }
    try {
      setFeedbackMessage(null);
      const replay = await replayVoiceResponse(sessionId);
      const fallbackText = isHi
        ? replay.speech_text || activeConversation?.message?.text_hi
        : replay.speech_text || activeConversation?.message?.text_en;

      if (replay.audio?.audio_url) {
        const streamUrl = resolveAudioUrl(replay.audio.audio_url, replay.audio.response_id);
        if (streamUrl) {
          playAudioStream(streamUrl, fallbackText);
          return;
        }
      }

      if (fallbackText) {
        speakBrowserSynthesis(fallbackText);
      }
    } catch (err: any) {
      console.warn('Voice replay notice:', err);
      const fallbackText = isHi
        ? activeConversation?.message?.text_hi
        : activeConversation?.message?.text_en;
      if (fallbackText) {
        speakBrowserSynthesis(fallbackText);
      }
    }
  }, [sessionId, isPlaying, stopPlayback, playAudioStream, resolveAudioUrl, speakBrowserSynthesis, activeConversation, isHi]);

  // Welcome greeting speech trigger
  const handleWelcomeSpeech = useCallback(() => {
    setHasUserInteracted(true);
    const welcome = isHi
      ? 'नमस्ते! मैं योजनसेतु आवाज़ सहायक हूँ। आप अपनी उम्र, कृषि भूमि, सामाजिक श्रेणी या पेंशन योजना के बारे में बोलकर पूछ सकते हैं।'
      : 'Hello! I am YojanSetu Voice Assistant. You can speak about your age, land, pension or government schemes to find your benefits.';
    speakBrowserSynthesis(welcome);
  }, [isHi, speakBrowserSynthesis]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, [stopPlayback]);

  return (
    <div className="w-full bg-linear-to-b from-indigo-50/80 via-white to-indigo-50/40 dark:from-slate-900 dark:via-slate-800/90 dark:to-slate-900 rounded-3xl border border-indigo-200/80 dark:border-slate-700/80 p-5 sm:p-8 shadow-2xl shadow-indigo-500/10 mb-6 transition-all">
      {/* Voice Mode Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 pb-4 border-b border-indigo-100 dark:border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-11 h-11 rounded-2xl bg-indigo-600 text-white font-bold text-2xl shadow-md shadow-indigo-600/30">
            🎙️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-slate-900 dark:text-slate-100 text-lg sm:text-xl">
                {isHi ? 'योजनसेतु — स्मार्ट आवाज़ सहायक' : 'YojanSetu — Smart Voice Assistant'}
              </h3>
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-bold text-[10px] uppercase tracking-wider">
                Live
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isHi
                ? 'राजस्थानी व हिंदी वाणी पहचान, नियम-आधारित पात्रता एवं त्वरित मौखिक उत्तर'
                : 'Vernacular Speech Recognition, Rule-Based Eligibility & Instant Vocal Reply'}
            </p>
          </div>
        </div>

        {/* Transport State Badge */}
        <VoiceStatus
          state={transportState}
          lang={lang}
          recordingDuration={recordingDuration}
        />
      </div>

      {/* Welcome Greeting Prompt for first-time entry */}
      {!hasUserInteracted && !isPlaying && !isRecording && (
        <div className="mb-5 p-4 rounded-2xl bg-indigo-500/10 dark:bg-indigo-500/15 border border-indigo-200 dark:border-indigo-800/50 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">👋</span>
            <span className="text-xs sm:text-sm font-semibold text-indigo-950 dark:text-indigo-200">
              {isHi
                ? 'नमस्ते! योजनसेतु से बातचीत शुरू करने के लिए स्वागत संदेश सुनें या सीधे बोलें।'
                : 'Welcome! Listen to the welcome audio or tap the mic to speak.'}
            </span>
          </div>
          <button
            type="button"
            onClick={handleWelcomeSpeech}
            className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-xs transition-transform hover:scale-105 active:scale-95 cursor-pointer flex items-center gap-1.5"
          >
            <span>🔊</span>
            <span>{isHi ? 'स्वागत संदेश सुनें' : 'Listen Welcome'}</span>
          </button>
        </div>
      )}

      {/* Permission Denied Alert */}
      {permissionState === 'denied' && (
        <div className="mb-6 p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/50 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3">
          <span className="text-xl">⚠️</span>
          <div className="flex-1">
            <p className="font-semibold mb-1">
              {isHi ? 'माइक्रोफ़ोन अनुमति नहीं मिली' : 'Microphone Permission Denied'}
            </p>
            <p className="text-xs opacity-90 mb-3">
              {isHi
                ? 'आवाज़ में बात करने के लिए ब्राउज़र के एड्रेस बार में माइक्रोफ़ोन की अनुमति दें, या नीचे दिए गए टेक्स्ट बॉक्स में लिखें।'
                : 'Enable microphone access in browser settings, or type your question below.'}
            </p>
          </div>
        </div>
      )}

      {/* Error / Warning Banners */}
      {errorMessage && (
        <div className="mb-4 p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/50 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span className="flex-1 font-medium">{errorMessage}</span>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-400 hover:text-rose-700 text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {feedbackMessage && (
        <div className="mb-4 p-3.5 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 text-amber-800 dark:text-amber-200 text-xs flex items-center gap-2">
          <span>ℹ️</span>
          <span className="flex-1 font-medium">{feedbackMessage}</span>
          <button
            type="button"
            onClick={() => setFeedbackMessage(null)}
            className="text-amber-500 hover:text-amber-800 text-xs font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Real-Time Reactive Audio Waveform Visualizer */}
      <AudioWaveform
        isRecording={isRecording}
        isPlaying={isPlaying}
        audioLevel={audioLevel}
        lang={lang}
      />

      {/* Live In-Progress Speech Recognition Feedback Bubble */}
      {isRecording && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/50 text-rose-900 dark:text-rose-200 text-xs sm:text-sm flex items-start gap-2.5 animate-pulse">
          <span className="text-base shrink-0">🎙️</span>
          <div>
            <span className="font-bold block text-[11px] uppercase tracking-wider text-rose-600 dark:text-rose-400">
              {isHi ? 'लाइव आवाज़ पहचान:' : 'Live Speech Recognized:'}
            </span>
            <span className="font-medium italic">
              {liveTranscript
                ? `“${liveTranscript}”`
                : isHi
                ? 'बोलिए, आपकी आवाज़ रिकॉर्ड हो रही है…'
                : 'Listening, speak your query now…'}
            </span>
          </div>
        </div>
      )}

      {/* Last Recognized Transcript (After Recording) */}
      {!isRecording && lastTranscript && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-200/60 dark:border-indigo-800/40 text-xs text-indigo-950 dark:text-indigo-200 flex items-center gap-2">
          <span className="font-bold shrink-0">{isHi ? 'आपने कहा:' : 'You said:'}</span>
          <span className="italic font-medium">“{lastTranscript}”</span>
        </div>
      )}

      {/* Assistant Voice Response Card */}
      {activeConversation?.message && (
        <div
          className={`mb-6 p-5 sm:p-6 rounded-2xl transition-all border ${
            isPlaying
              ? 'bg-emerald-50/90 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-700/60 shadow-lg shadow-emerald-500/10 ring-2 ring-emerald-500/30'
              : 'bg-white dark:bg-slate-800/90 border-slate-200/80 dark:border-slate-700/60 shadow-sm'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{isPlaying ? '🔊' : '🏛️'}</span>
              <span className="text-xs font-extrabold uppercase tracking-wider text-slate-600 dark:text-slate-300">
                {isHi ? 'योजनसेतु का उत्तर' : "YojanSetu's Response"}
              </span>
              {isPlaying && (
                <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/60 px-2.5 py-0.5 rounded-full animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  {isHi ? 'बोल रहा है…' : 'Speaking…'}
                </span>
              )}
            </div>

            {/* Replay mini button */}
            <button
              type="button"
              onClick={handleReplay}
              disabled={isPlaying || isRecording}
              className="text-xs font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 flex items-center gap-1 cursor-pointer disabled:opacity-40"
              title={isHi ? 'दोबारा सुनें' : 'Listen again'}
            >
              <span>🔊</span>
              <span>{isHi ? 'दोबारा सुनें' : 'Listen'}</span>
            </button>
          </div>

          <p className="text-sm sm:text-base font-medium text-slate-800 dark:text-slate-100 leading-relaxed whitespace-pre-wrap">
            {isHi ? activeConversation.message.text_hi : activeConversation.message.text_en}
          </p>

          {/* If Eligible Schemes Discovered */}
          {activeConversation.results?.eligible && activeConversation.results.eligible.length > 0 && (
            <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-700/50 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs sm:text-sm font-extrabold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                <span>🎉</span>
                <span>
                  {isHi
                    ? `${activeConversation.results.eligible.length} सरकारी योजनाएँ आपके लिए पात्र पाई गईं!`
                    : `${activeConversation.results.eligible.length} Eligible welfare schemes found!`}
                </span>
              </span>
              <button
                type="button"
                onClick={onSwitchToText}
                className="text-xs font-bold px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl shadow-xs transition-colors cursor-pointer"
              >
                {isHi ? 'विस्तृत विवरण व पर्ची देखें ➔' : 'View Full Details & Slip ➔'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Voice Controls with Push-to-Talk, Quick Suggestions & In-Voice Text Bar */}
      <VoiceControls
        state={transportState}
        isRecording={isRecording}
        isPlaying={isPlaying}
        onStartRecord={startRecordingSafe}
        onStopRecord={stopRecording}
        onStopSpeaking={stopPlayback}
        onReplay={handleReplay}
        onQuickQuery={handleQuickQuery}
        onSwitchToText={onSwitchToText}
        onStartOver={onStartOver}
        onEndConversation={onEndConversation}
        disabled={permissionState === 'denied'}
        lang={lang}
      />
    </div>
  );
}
