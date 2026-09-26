'use client';

import React, { useState } from 'react';
import { VoiceTransportState } from '@/types/voice';

interface VoiceControlsProps {
  state: VoiceTransportState;
  isRecording: boolean;
  isPlaying: boolean;
  onStartRecord: () => void;
  onStopRecord: () => void;
  onStopSpeaking: () => void;
  onReplay: () => void;
  onQuickQuery: (text: string) => void;
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
  onQuickQuery,
  onSwitchToText,
  onStartOver,
  onEndConversation,
  disabled = false,
  lang = 'hi',
}: VoiceControlsProps) {
  const isHi = lang === 'hi';
  const [typedInput, setTypedInput] = useState('');

  const isProcessing =
    state === 'PROCESSING_AUDIO' ||
    state === 'TRANSCRIBING' ||
    state === 'PROCESSING_TURN' ||
    state === 'SYNTHESIZING';

  const quickPrompts = isHi
    ? [
        { label: '👴 65 वर्ष, पेंशन योजना', query: 'मेरी उम्र 65 वर्ष है, मुझे वृद्धजन पेंशन योजना की जानकारी चाहिए।' },
        { label: '🌾 3 बीघा ज़मीन, किसान सहायता', query: 'मेरे पास 3 बीघा कृषि भूमि है, मुझे किसान सम्मान निधि और सरकारी सहायता चाहिए।' },
        { label: '👩 एकल नारी / विधवा पेंशन', query: 'मैं विधवा महिला हूँ, मुझे राजस्थान एकल नारी पेंशन योजना का लाभ चाहिए।' },
        { label: '🎓 छात्र निःशुल्क कोचिंग', query: 'मैं 12वीं पास छात्र हूँ, अनुप्रति कोचिंग योजना की पात्रता क्या है?' },
        { label: '🏥 ₹25 लाख मुफ्त स्वास्थ्य उपचार', query: 'आयुष्मान आरोग्य स्वास्थ्य योजना में ₹25 लाख कैशलेस इलाज कैसे मिलेगा?' },
      ]
    : [
        { label: '👴 65 yrs, Senior Pension', query: 'I am 65 years old. What senior pension schemes am I eligible for?' },
        { label: '🌾 Small Farmer Support', query: 'I have 3 bighas of agricultural land. What farmer benefits can I receive?' },
        { label: '👩 Widow / Single Woman Pension', query: 'I am a widow in Rajasthan. How can I apply for Ekal Nari pension?' },
        { label: '🎓 Free Student Coaching', query: 'What are the eligibility criteria for Anuprati Free Coaching Scheme?' },
        { label: '🏥 ₹25L Free Healthcare', query: 'How does the Ayushman Arogya 25 lakh cashless healthcare coverage work?' },
      ];

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedInput.trim() || isProcessing || isRecording) return;
    onQuickQuery(typedInput.trim());
    setTypedInput('');
  };

  return (
    <div className="flex flex-col items-center gap-5 w-full">
      {/* Primary Voice Action Center */}
      <div className="relative flex items-center justify-center">
        {isPlaying ? (
          // Stop speaking button
          <button
            type="button"
            onClick={onStopSpeaking}
            className="flex items-center justify-center gap-3 px-8 py-4 sm:py-5 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white font-bold text-base sm:text-lg shadow-lg shadow-amber-500/30 transition-all hover:scale-105 active:scale-95 cursor-pointer"
            aria-label={isHi ? 'आवाज़ रोकें' : 'Stop voice'}
          >
            <span className="text-2xl">⏹️</span>
            <span>{isHi ? 'आवाज़ रोकें' : 'Stop Voice'}</span>
          </button>
        ) : isRecording ? (
          // Stop & send recording button
          <button
            type="button"
            onClick={onStopRecord}
            className="flex items-center justify-center gap-3 px-8 py-4 sm:py-5 rounded-2xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-base sm:text-lg shadow-xl shadow-rose-600/40 animate-pulse transition-all hover:scale-105 active:scale-95 cursor-pointer ring-4 ring-rose-300 dark:ring-rose-800"
            aria-label={isHi ? 'बोलना पूरा हुआ (भेजें)' : 'Done Speaking (Send)'}
          >
            <span className="text-2xl">⏹️</span>
            <span>{isHi ? 'बोलना पूरा हुआ (भेजें)' : 'Done Speaking (Send)'}</span>
          </button>
        ) : (
          // Tap to speak button
          <button
            type="button"
            onClick={onStartRecord}
            disabled={disabled || isProcessing}
            className={`flex items-center justify-center gap-3 px-9 py-5 rounded-2xl font-bold text-base sm:text-lg shadow-xl transition-all cursor-pointer ${
              isProcessing
                ? 'bg-slate-400 text-white cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-600/30 hover:scale-105 active:scale-95 ring-4 ring-indigo-200 dark:ring-indigo-900/60'
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
                <span className="text-2xl animate-bounce">🎙️</span>
                <span>{isHi ? 'बोलने के लिए दबाएँ' : 'Tap to Speak'}</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Quick Interactive Prompt Suggestions */}
      {!isRecording && !isProcessing && (
        <div className="w-full flex flex-col items-center gap-2 mt-1">
          <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            {isHi ? '⚡ या सीधे किसी विषय पर पूछें (क्लिक करें):' : '⚡ Or tap to ask about a common topic:'}
          </span>
          <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl">
            {quickPrompts.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onQuickQuery(chip.query)}
                className="px-3.5 py-1.5 rounded-full bg-indigo-50/80 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/50 border border-indigo-200/70 dark:border-indigo-800/50 text-indigo-700 dark:text-indigo-300 text-xs font-medium transition-all hover:scale-105 active:scale-95 cursor-pointer shadow-2xs"
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quick In-Voice Text Query Bar */}
      {!isRecording && (
        <form onSubmit={handleManualSubmit} className="w-full max-w-lg flex items-center gap-2 mt-2">
          <input
            type="text"
            value={typedInput}
            onChange={(e) => setTypedInput(e.target.value)}
            disabled={isProcessing}
            placeholder={
              isHi
                ? 'माइक काम न करे तो यहाँ टाइप करें (उदा: मेरी उम्र 60 साल है)…'
                : 'Or type your question here (e.g. I am 60 yrs old)...'
            }
            className="flex-1 px-4 py-2 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 shadow-2xs"
          />
          <button
            type="submit"
            disabled={!typedInput.trim() || isProcessing}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs sm:text-sm transition-colors disabled:opacity-40 cursor-pointer shadow-2xs"
          >
            {isHi ? 'भेजें' : 'Send'}
          </button>
        </form>
      )}

      {/* Secondary Controls Bar */}
      <div className="flex flex-wrap items-center justify-center gap-3 pt-2 border-t border-indigo-100/60 dark:border-slate-700/40 w-full text-xs">
        {/* Replay last response */}
        <button
          type="button"
          onClick={onReplay}
          disabled={isRecording || isProcessing || isPlaying}
          className="px-3.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5"
          title={isHi ? 'योजनसेतु की बात दोबारा सुनें' : 'Listen again'}
        >
          <span>🔊</span>
          <span>{isHi ? 'दोबारा सुनें' : 'Replay Voice'}</span>
        </button>

        {/* Switch to text agent mode */}
        <button
          type="button"
          onClick={onSwitchToText}
          className="px-3.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
        >
          <span>⌨️</span>
          <span>{isHi ? 'विस्तृत टेक्स्ट मोड' : 'Switch to Text'}</span>
        </button>

        {/* Start over */}
        {onStartOver && (
          <button
            type="button"
            onClick={onStartOver}
            className="px-3.5 py-1.5 rounded-xl text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>🔄</span>
            <span>{isHi ? 'नया सत्र' : 'Start Over'}</span>
          </button>
        )}

        {/* End */}
        {onEndConversation && (
          <button
            type="button"
            onClick={onEndConversation}
            className="px-3.5 py-1.5 rounded-xl text-rose-500 hover:text-rose-700 font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <span>✕</span>
            <span>{isHi ? 'समाप्त करें' : 'End'}</span>
          </button>
        )}
      </div>
    </div>
  );
}
