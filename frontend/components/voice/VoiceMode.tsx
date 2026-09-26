'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { VoiceTransportState, VoiceTurnResponse } from '@/types/voice';
import { ConversationTurnResponse } from '@/types/citizen';
import {
  sendVoiceTurn,
  getVoiceResponseAudioUrl,
  replayVoiceResponse,
  ApiError,
} from '@/lib/api';
import { config } from '@/lib/config';
import { useVoiceRecorder } from './useVoiceRecorder';
import { VoiceStatus } from './VoiceStatus';
import { VoiceControls } from './VoiceControls';

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

  // Web Speech Synthesis browser fallback
  const speakBrowserSynthesis = useCallback(
    (text: string) => {
      stopPlayback();
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = isHi ? 'hi-IN' : 'en-IN';
        utterance.rate = 1.0;
        setIsPlaying(true);
        setTransportState('SPEAKING');

        utterance.onend = () => {
          setIsPlaying(false);
          setTransportState('READY');
        };

        utterance.onerror = (e) => {
          console.warn('SpeechSynthesis error:', e);
          setIsPlaying(false);
          setTransportState('READY');
        };

        window.speechSynthesis.speak(utterance);
      } else {
        setTransportState('READY');
      }
    },
    [isHi, stopPlayback]
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
        console.warn('Audio playback error:', err, 'falling back to speech synthesis');
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

  // Voice Turn Submission Handler
  const handleRecordingComplete = useCallback(
    async (audioBlob: Blob, liveTranscript?: string) => {
      setTransportState('PROCESSING_AUDIO');
      setErrorMessage(null);
      setFeedbackMessage(null);

      if (liveTranscript) {
        setLastTranscript(liveTranscript);
      }

      // Generate client-side idempotency turn token
      const voiceTurnId = `vturn_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      try {
        setTransportState('TRANSCRIBING');
        const turnResult: VoiceTurnResponse = await sendVoiceTurn(
          sessionId,
          audioBlob,
          voiceTurnId,
          activeConversation?.meta?.version ?? conversationVersion,
          liveTranscript,
          lang
        );

        // Update transcript if available
        if (turnResult.transcription?.text) {
          setLastTranscript(turnResult.transcription.text);
        }

        // Forward structured conversation response to parent CitizenPage
        if (turnResult.conversation) {
          setActiveConversation(turnResult.conversation);
          onConversationResponse(turnResult.conversation);
        }

        // Handle retry warnings (e.g. no speech detected or empty STT)
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
                ? 'आवाज़ प्रोसेस करने में त्रुटि हुई। कृपया दोबारा बोलें या टेक्स्ट में लिखें।'
                : 'Error processing voice. Please speak again or type in text.')
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

  // MediaRecorder + SpeechRecognition hook
  const {
    isRecording,
    permissionState,
    recordingDuration,
    startRecording: triggerStartRecording,
    stopRecording,
  } = useVoiceRecorder({
    maxDurationSeconds: 60,
    lang,
    onRecordingComplete: handleRecordingComplete,
    onError: (err) => {
      setTransportState('READY');
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage(
          isHi
            ? 'माइक्रोफ़ोन की अनुमति आवश्यक है। आप टेक्स्ट मोड जारी रख सकते हैं।'
            : 'Microphone permission is required. You can continue in text mode.'
        );
      } else {
        setErrorMessage(err.message);
      }
    },
  });

  // Half-duplex guard: Prevent starting microphone while speaking
  const startRecordingSafe = useCallback(() => {
    if (isPlaying) {
      stopPlayback();
    }
    setTransportState('LISTENING');
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

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, [stopPlayback]);

  return (
    <div className="w-full bg-gradient-to-b from-indigo-50/70 to-white dark:from-slate-900 dark:to-slate-800/80 rounded-3xl border border-indigo-100 dark:border-slate-700/60 p-6 md:p-8 shadow-xl shadow-indigo-500/5 mb-6">
      {/* Voice Mode Header */}
      <div className="flex items-center justify-between gap-4 mb-6 pb-4 border-b border-indigo-100/60 dark:border-slate-700/40">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-indigo-600 text-white font-bold text-xl shadow-md shadow-indigo-600/20">
            🎙️
          </div>
          <div>
            <h3 className="font-bold text-slate-800 dark:text-slate-100 text-lg">
              {isHi ? 'योजनसेतु — आवाज़ सहायक' : 'YojanSetu — Voice Assistant'}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isHi
                ? 'ऑफ़लाइन हिंदी वाणी पहचान एवं सुरक्षित उत्तर'
                : 'Offline Vernacular Speech Recognition & Synthesis'}
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
                ? 'आवाज़ में बात करने के लिए ब्राउज़र में माइक्रोफ़ोन की अनुमति दें, अथवा टेक्स्ट मोड का उपयोग करें।'
                : 'Please enable microphone access in browser settings or continue using text mode.'}
            </p>
            <button
              type="button"
              onClick={onSwitchToText}
              className="px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition-colors cursor-pointer"
            >
              {isHi ? 'टेक्स्ट मोड में जाएँ' : 'Switch to Text'}
            </button>
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
            className="text-rose-400 hover:text-rose-700 text-xs font-bold"
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
            className="text-amber-500 hover:text-amber-800 text-xs font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Transcript feedback if available */}
      {lastTranscript && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-200/50 dark:border-indigo-800/40 text-xs text-indigo-900 dark:text-indigo-200 flex items-center gap-2">
          <span className="font-semibold">{isHi ? 'मैंने सुना:' : 'Heard:'}</span>
          <span className="italic font-medium">“{lastTranscript}”</span>
        </div>
      )}

      {/* Assistant Voice Response Card */}
      {activeConversation?.message && (
        <div
          className={`mb-6 p-5 rounded-2xl transition-all border ${
            isPlaying
              ? 'bg-emerald-50/80 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-700/60 shadow-md shadow-emerald-500/10 ring-2 ring-emerald-500/20'
              : 'bg-white dark:bg-slate-800/90 border-slate-200/80 dark:border-slate-700/60 shadow-sm'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-base">{isPlaying ? '🔊' : '🏛️'}</span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {isHi ? 'योजनसेतु का उत्तर' : "YojanSetu's Response"}
              </span>
              {isPlaying && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/60 px-2 py-0.5 rounded-full animate-pulse">
                  <span>●</span> {isHi ? 'बोल रहा है…' : 'Speaking…'}
                </span>
              )}
            </div>

            {/* Replay mini button */}
            <button
              type="button"
              onClick={handleReplay}
              disabled={isPlaying || isRecording}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 flex items-center gap-1 cursor-pointer disabled:opacity-40"
              title={isHi ? 'दोबारा सुनें' : 'Listen again'}
            >
              <span>🔊</span>
              <span>{isHi ? 'सुनें' : 'Listen'}</span>
            </button>
          </div>

          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">
            {isHi ? activeConversation.message.text_hi : activeConversation.message.text_en}
          </p>

          {/* If Eligible Schemes Discovered */}
          {activeConversation.results?.eligible && activeConversation.results.eligible.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700/50 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400">
                🎉{' '}
                {isHi
                  ? `${activeConversation.results.eligible.length} योजनाएँ पात्र पाई गईं!`
                  : `${activeConversation.results.eligible.length} Eligible schemes found!`}
              </span>
              <button
                type="button"
                onClick={onSwitchToText}
                className="text-xs font-semibold px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors cursor-pointer"
              >
                {isHi ? 'योजनाएँ देखें' : 'View Schemes'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Voice Controls with Push-to-Talk Button */}
      <VoiceControls
        state={transportState}
        isRecording={isRecording}
        isPlaying={isPlaying}
        onStartRecord={startRecordingSafe}
        onStopRecord={stopRecording}
        onStopSpeaking={stopPlayback}
        onReplay={handleReplay}
        onSwitchToText={onSwitchToText}
        onStartOver={onStartOver}
        onEndConversation={onEndConversation}
        disabled={permissionState === 'denied'}
        lang={lang}
      />
    </div>
  );
}
