'use client';

import React from 'react';
import { VoiceTransportState } from '@/types/voice';

interface VoiceControlsProps {
  state: VoiceTransportState;
  isRecording: boolean;
  isPlaying: boolean;
  onStartRecord: () => void;
  onStopRecord: () => void;
  onStopSpeaking: () => void;
  onReplay: () => void;
  onSwitchToText: () => void;
  onStartOver?: () => void;
  onEndConversation?: () => void;
  disabled?: boolean;
  lang?: 'hi' | 'en';
}

export function VoiceControls({
  state,
  isRecording,
  isPlaying,
  onStartRecord,
  onStopRecord,
  onStopSpeaking,
  onReplay,
  onSwitchToText,
  onStartOver,
  onEndConversation,
  disabled = false,
  lang = 'hi',
}: VoiceControlsProps) {
  const isHi = lang === 'hi';
  const isProcessing =
    state === 'PROCESSING_AUDIO' ||
    state === 'TRANSCRIBING' ||
    state === 'PROCESSING_TURN' ||
    state === 'SYNTHESIZING';

  return (
    <div className="flex flex-col items-center gap-4 w-full">
      {/* Primary Push-to-Talk / Control Button */}
      <div className="relative flex items-center justify-center">
        {isPlaying ? (
          // Stop playback button while JanSetu is speaking
          <button
            type="button"
            onClick={onStopSpeaking}
            className="flex items-center justify-center gap-3 px-8 py-5 rounded-2xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-lg shadow-lg shadow-amber-600/30 transition-all hover:scale-105 active:scale-95"
            aria-label={isHi ? 'आवाज़ रोकें' : 'Stop voice'}
          >
            <span className="text-2xl">⏹️</span>
            <span>{isHi ? 'आवाज़ रोकें' : 'Stop Voice'}</span>
          </button>
        ) : isRecording ? (
          // Stop recording button while citizen is speaking
          <button
            type="button"
            onClick={onStopRecord}
            className="flex items-center justify-center gap-3 px-8 py-5 rounded-2xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-lg shadow-lg shadow-rose-600/30 animate-pulse transition-all hover:scale-105 active:scale-95"
            aria-label={isHi ? 'बोलना पूरा हुआ (भेजें)' : 'Stop recording'}
          >
            <span className="text-2xl">⏹️</span>
            <span>{isHi ? 'बोलना पूरा हुआ (भेजें)' : 'Stop & Send'}</span>
          </button>
        ) : (
          // Tap to speak button when ready
          <button
            type="button"
            onClick={onStartRecord}
            disabled={disabled || isProcessing}
            className={`flex items-center justify-center gap-3 px-8 py-5 rounded-2xl font-bold text-lg shadow-lg transition-all ${
              isProcessing
                ? 'bg-slate-400 text-slate-100 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-600/30 hover:scale-105 active:scale-95'
            }`}
            aria-label={isHi ? 'बोलने के लिए दबाएँ' : 'Tap to speak'}
          >
            {isProcessing ? (
              <>
                <span className="inline-block w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>{isHi ? 'समझ रहा हूँ…' : 'Processing…'}</span>
              </>
            ) : (
              <>
                <span className="text-2xl">🎙️</span>
                <span>{isHi ? 'बोलने के लिए दबाएँ' : 'Tap to Speak'}</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Secondary Controls Bar */}
      <div className="flex flex-wrap items-center justify-center gap-3 mt-2 text-sm">
        {/* Replay last response */}
        <button
          type="button"
          onClick={onReplay}
          disabled={isRecording || isProcessing || isPlaying}
          className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition-colors disabled:opacity-50"
          title={isHi ? 'जनसेतु की पिछली बात दोबारा सुनें' : 'Replay last response'}
        >
          🔊 {isHi ? 'दोबारा सुनें' : 'Replay'}
        </button>

        {/* Switch to text */}
        <button
          type="button"
          onClick={onSwitchToText}
          className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition-colors"
        >
          ⌨️ {isHi ? 'टाइप करके लिखें' : 'Switch to Text'}
        </button>

        {/* Start over */}
        {onStartOver && (
          <button
            type="button"
            onClick={onStartOver}
            className="px-4 py-2 rounded-xl text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
          >
            🔄 {isHi ? 'नया सत्र' : 'Start Over'}
          </button>
        )}

        {/* End */}
        {onEndConversation && (
          <button
            type="button"
            onClick={onEndConversation}
            className="px-4 py-2 rounded-xl text-rose-500 hover:text-rose-700 transition-colors"
          >
            ✕ {isHi ? 'समाप्त करें' : 'End'}
          </button>
        )}
      </div>
    </div>
  );
}
