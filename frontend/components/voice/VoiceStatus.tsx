'use client';

import React from 'react';
import { VoiceTransportState } from '@/types/voice';

interface VoiceStatusProps {
  state: VoiceTransportState;
  lang?: 'hi' | 'en';
  recordingDuration?: number;
}

export function VoiceStatus({ state, lang = 'hi', recordingDuration = 0 }: VoiceStatusProps) {
  const isHi = lang === 'hi';

  const getStatusConfig = () => {
    switch (state) {
      case 'LISTENING':
        return {
          label: isHi ? `सुन रहा हूँ… (${recordingDuration}s)` : `Listening… (${recordingDuration}s)`,
          badgeClass: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 animate-pulse',
          dotClass: 'bg-red-500 animate-ping',
        };
      case 'PROCESSING_AUDIO':
      case 'TRANSCRIBING':
      case 'PROCESSING_TURN':
      case 'SYNTHESIZING':
        return {
          label: isHi ? 'समझ रहा हूँ…' : 'Processing…',
          badgeClass: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
          dotClass: 'bg-amber-500 animate-spin',
        };
      case 'SPEAKING':
        return {
          label: isHi ? 'जनसेतु बोल रहा है…' : 'JanSetu is speaking…',
          badgeClass: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 animate-pulse',
          dotClass: 'bg-emerald-500',
        };
      case 'RECOVERABLE_ERROR':
        return {
          label: isHi ? 'पुनः प्रयास करें' : 'Try Again',
          badgeClass: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
          dotClass: 'bg-rose-500',
        };
      case 'READY':
      default:
        return {
          label: isHi ? 'तैयार' : 'Ready',
          badgeClass: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
          dotClass: 'bg-blue-500',
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold tracking-wide transition-all ${config.badgeClass}`}
    >
      <span className={`w-2 h-2 rounded-full ${config.dotClass}`} />
      <span>{config.label}</span>
    </div>
  );
}
