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
import { useVoiceRecorder } from './useVoiceRecorder';
import { VoiceStatus } from './VoiceStatus';
import { VoiceControls } from './VoiceControls';

interface VoiceModeProps {
  sessionId: string;
  conversationVersion?: number;
  lang?: 'hi' | 'en';
  onConversationResponse: (response: ConversationTurnResponse) => void;
  onSwitchToText: () => void;
  onStartOver?: () => void;
  onEndConversation?: () => void;
}

export function VoiceMode({
  sessionId,
  conversationVersion,
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

  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const audioBlobUrlRef = useRef<string | null>(null);

  // Stop audio playback cleanly
  const stopPlayback = useCallback(() => {
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

  // Play synthesized audio stream enforcing half-duplex rules
  const playAudioStream = useCallback((audioUrl: string) => {
    stopPlayback();

    const audio = new Audio(audioUrl);
    audioPlayerRef.current = audio;
    setIsPlaying(true);
    setTransportState('SPEAKING');

    audio.onended = () => {
      stopPlayback();
    };

    audio.onerror = (err) => {
      console.warn('Audio playback error:', err);
      stopPlayback();
      setFeedbackMessage(
        isHi
          ? 'ऑडियो प्लेबैक में समस्या आई। आप उत्तर स्क्रीन पर पढ़ सकते हैं।'
          : 'Audio playback encountered an issue. You can read the response on screen.'
      );
    };

    audio.play().catch((playErr) => {
      console.warn('Browser prevented audio autoplay:', playErr);
      stopPlayback();
    });
  }, [isHi, stopPlayback]);

  // Voice Turn Submission Handler
  const handleRecordingComplete = useCallback(
    async (audioBlob: Blob) => {
      setTransportState('PROCESSING_AUDIO');
      setErrorMessage(null);
      setFeedbackMessage(null);

      // Generate client-side idempotency turn token
      const voiceTurnId = `vturn_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      try {
        setTransportState('TRANSCRIBING');
        const turnResult: VoiceTurnResponse = await sendVoiceTurn(
          sessionId,
          audioBlob,
          voiceTurnId,
          conversationVersion
        );

        // Update transcript if available
        if (turnResult.transcription?.text) {
          setLastTranscript(turnResult.transcription.text);
        }

        // Forward structured conversation response to parent CitizenPage
        if (turnResult.conversation) {
          onConversationResponse(turnResult.conversation);
        }

        // Handle retry warnings (e.g. no speech detected or empty STT)
        if (turnResult.warning) {
          setFeedbackMessage(turnResult.warning);
        }

        // Play synthesized TTS audio if provided
        if (turnResult.audio?.audio_url) {
          playAudioStream(turnResult.audio.audio_url);
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
    [sessionId, conversationVersion, isHi, onConversationResponse, playAudioStream]
  );

  // MediaRecorder hook
  const {
    isRecording,
    permissionState,
    recordingDuration,
    startRecording: triggerStartRecording,
    stopRecording,
  } = useVoiceRecorder({
    maxDurationSeconds: 60,
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
      if (replay.audio?.audio_url) {
        playAudioStream(replay.audio.audio_url);
      }
    } catch (err: any) {
      console.warn('Voice replay failed:', err);
      setFeedbackMessage(
        isHi ? 'पुनः आवाज़ चलाने में असमर्थ।' : 'Unable to replay audio response.'
      );
    }
  }, [sessionId, isPlaying, stopPlayback, playAudioStream, isHi]);

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
              {isHi ? 'योजनसेतु — आवाज़ मोड' : 'YojanSetu — Voice Mode'}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isHi
                ? 'ऑफ़लाइन हिंदी वाणी पहचान एवं उत्तर'
                : 'Offline Hindi Speech Recognition & Synthesis'}
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
              className="px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition-colors"
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
          <span className="flex-1">{errorMessage}</span>
        </div>
      )}

      {feedbackMessage && (
        <div className="mb-4 p-3.5 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/50 text-amber-800 dark:text-amber-200 text-xs flex items-center gap-2">
          <span>ℹ️</span>
          <span className="flex-1">{feedbackMessage}</span>
        </div>
      )}

      {/* Transcript feedback if available */}
      {lastTranscript && (
        <div className="mb-6 px-4 py-3 rounded-2xl bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-200/50 dark:border-indigo-800/40 text-xs text-indigo-900 dark:text-indigo-200 flex items-center gap-2">
          <span className="font-semibold">{isHi ? 'मैंने सुना:' : 'Heard:'}</span>
          <span className="italic">“{lastTranscript}”</span>
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
