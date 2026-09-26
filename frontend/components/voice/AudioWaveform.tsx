'use client';

import React from 'react';

interface AudioWaveformProps {
  isRecording: boolean;
  isPlaying: boolean;
  audioLevel: number; // 0 to 100
  lang?: 'hi' | 'en';
}

export function AudioWaveform({
  isRecording,
  isPlaying,
  audioLevel,
  lang = 'hi',
}: AudioWaveformProps) {
  const isHi = lang === 'hi';

  // 12 reactive waveform bars with varied height multipliers
  const multipliers = [0.4, 0.7, 1.0, 1.3, 0.9, 1.4, 1.2, 0.8, 1.1, 0.6, 0.8, 0.5];

  return (
    <div className="flex flex-col items-center justify-center py-3 w-full">
      {/* Audio Visualizer Waves Container */}
      <div className="flex items-center justify-center gap-1.5 h-16 px-4">
        {multipliers.map((mult, index) => {
          let heightPx = 6;

          if (isRecording) {
            // Scale dynamically with actual microphone volume
            const variableBoost = Math.sin((index + Date.now() / 200) * 0.8) * 6;
            heightPx = Math.max(6, Math.min(56, Math.round(audioLevel * mult * 0.55 + variableBoost)));
          } else if (isPlaying) {
            // Smooth undulating wave for assistant speech synthesis
            heightPx = Math.max(8, Math.min(48, Math.round(18 + Math.sin(index * 0.6 + Date.now() / 150) * 16)));
          }

          return (
            <span
              key={index}
              style={{
                height: `${heightPx}px`,
                transition: isRecording ? 'height 80ms ease' : 'height 120ms ease',
              }}
              className={`w-1.5 rounded-full ${
                isRecording
                  ? audioLevel > 20
                    ? 'bg-rose-500 shadow-xs shadow-rose-500/50'
                    : 'bg-indigo-400/80 dark:bg-indigo-500/60'
                  : isPlaying
                  ? 'bg-emerald-500 shadow-xs shadow-emerald-500/50 animate-pulse'
                  : 'bg-slate-300 dark:bg-slate-600'
              }`}
            />
          );
        })}
      </div>

      {/* Visual Activity Caption */}
      <div className="text-[11px] font-semibold text-center mt-1">
        {isRecording ? (
          <span className="text-rose-600 dark:text-rose-400 flex items-center justify-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
            {audioLevel > 15
              ? isHi
                ? 'आवाज़ पहचानी जा रही है…'
                : 'Detecting speech…'
              : isHi
              ? 'कृपया बोलिए, माइक सक्रिय है…'
              : 'Speak now, mic is listening…'}
          </span>
        ) : isPlaying ? (
          <span className="text-emerald-600 dark:text-emerald-400 flex items-center justify-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            {isHi ? 'योजनसेतु उत्तर सुना रहा है…' : 'YojanSetu is speaking…'}
          </span>
        ) : (
          <span className="text-slate-400 dark:text-slate-500">
            {isHi ? 'बोलने के लिए माइक बटन दबाएँ या सुझाव चुनें' : 'Tap mic or choose a suggestion to talk'}
          </span>
        )}
      </div>
    </div>
  );
}
