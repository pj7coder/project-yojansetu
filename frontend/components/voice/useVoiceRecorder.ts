'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

export type MicPermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

interface UseVoiceRecorderOptions {
  maxDurationSeconds?: number;
  silenceTimeoutSeconds?: number;
  autoStopOnSilence?: boolean;
  lang?: 'hi' | 'en';
  onRecordingComplete: (audioBlob: Blob, transcript?: string) => void;
  onError?: (error: Error) => void;
}

export function useVoiceRecorder({
  maxDurationSeconds = 60,
  silenceTimeoutSeconds = 2.4,
  autoStopOnSilence = true,
  lang = 'hi',
  onRecordingComplete,
  onError,
}: UseVoiceRecorderOptions) {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [permissionState, setPermissionState] = useState<MicPermissionState>('prompt');
  const [recordingDuration, setRecordingDuration] = useState<number>(0);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [liveTranscript, setLiveTranscript] = useState<string>('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef<string>('');
  const chunksRef = useRef<Blob[]>([]);
  const isRecordingRef = useRef<boolean>(false);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const durationTimerRef = useRef<NodeJS.Timeout | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const hasSpokenRef = useRef<boolean>(false);

  const isSupported = typeof window !== 'undefined' && !!navigator?.mediaDevices?.getUserMedia;

  // Cleanup Web Audio & Stream
  const cleanupAudio = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  // Determine best supported MIME type
  const getSupportedMimeType = (): string => {
    if (typeof MediaRecorder === 'undefined') return 'audio/webm';
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];
    for (const t of types) {
      if (MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return '';
  };

  // Stop recording safely
  const stopRecording = useCallback(() => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;
    clearTimers();

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.warn('Error stopping MediaRecorder:', err);
      }
    }
  }, [clearTimers]);

  // Audio level monitoring loop using Web Audio API Analyser
  const setupAudioMeter = useCallback((stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;

      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.5;
      source.connect(analyser);

      audioContextRef.current = audioCtx;
      analyserRef.current = analyser;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const checkVolume = () => {
        if (!analyserRef.current || !isRecordingRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);

        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const avg = sum / bufferLength;
        const normalized = Math.min(100, Math.round((avg / 128) * 100));
        setAudioLevel(normalized);

        // Sound activity detection
        if (normalized > 12) {
          hasSpokenRef.current = true;
          // Reset silence timer on sound detection
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (hasSpokenRef.current && autoStopOnSilence && isRecordingRef.current) {
          // If citizen spoke and is now quiet for silenceTimeoutSeconds, trigger auto-stop
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              if (isRecordingRef.current && (transcriptRef.current.length > 2 || hasSpokenRef.current)) {
                stopRecording();
              }
            }, silenceTimeoutSeconds * 1000);
          }
        }

        animFrameRef.current = requestAnimationFrame(checkVolume);
      };

      animFrameRef.current = requestAnimationFrame(checkVolume);
    } catch (err) {
      console.warn('Web Audio meter not available:', err);
    }
  }, [autoStopOnSilence, silenceTimeoutSeconds, stopRecording]);

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      setPermissionState('unavailable');
      onError?.(new Error('Browser does not support audio recording.'));
      return;
    }

    try {
      cleanupAudio();
      clearTimers();
      chunksRef.current = [];
      transcriptRef.current = '';
      hasSpokenRef.current = false;
      setLiveTranscript('');
      setRecordingDuration(0);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      mediaStreamRef.current = stream;
      setPermissionState('granted');
      isRecordingRef.current = true;
      setIsRecording(true);

      // Start Web Audio meter for reactive visualizer
      setupAudioMeter(stream);

      // Initialize Web Speech API for instantaneous transcription feedback
      const SpeechRec =
        typeof window !== 'undefined'
          ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
          : null;

      if (SpeechRec) {
        try {
          const recognition = new SpeechRec();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = lang === 'en' ? 'en-IN' : 'hi-IN';

          recognition.onresult = (e: any) => {
            let fullText = '';
            for (let i = 0; i < e.results.length; i++) {
              fullText += e.results[i][0].transcript + ' ';
            }
            const clean = fullText.trim();
            transcriptRef.current = clean;
            setLiveTranscript(clean);

            if (clean.length > 0) {
              hasSpokenRef.current = true;
              // Reset silence timer on fresh speech tokens
              if (silenceTimerRef.current) {
                clearTimeout(silenceTimerRef.current);
                silenceTimerRef.current = null;
              }
              if (autoStopOnSilence && isRecordingRef.current) {
                silenceTimerRef.current = setTimeout(() => {
                  if (isRecordingRef.current) {
                    stopRecording();
                  }
                }, silenceTimeoutSeconds * 1000);
              }
            }
          };

          recognition.onerror = (e: any) => {
            if (e.error !== 'no-speech') {
              console.warn('SpeechRecognition notice:', e.error);
            }
          };

          // Auto-recover recognition if browser terminates continuous stream before user stops
          recognition.onend = () => {
            if (isRecordingRef.current) {
              try {
                recognition.start();
              } catch {}
            }
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (recErr) {
          console.warn('SpeechRecognition initialization note:', recErr);
        }
      }

      const mimeType = getSupportedMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        isRecordingRef.current = false;
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {}
          recognitionRef.current = null;
        }

        const fullBlob = new Blob(chunksRef.current, {
          type: mimeType || 'audio/webm',
        });
        const finalTranscript = transcriptRef.current;

        chunksRef.current = [];
        cleanupAudio();
        clearTimers();
        setIsRecording(false);

        // Ensure we pass final audio and recognized transcript
        onRecordingComplete(fullBlob, finalTranscript);
      };

      recorder.start(200); // 200ms slice chunks

      // Duration counter
      const startTime = Date.now();
      durationTimerRef.current = setInterval(() => {
        setRecordingDuration(Math.round((Date.now() - startTime) / 1000));
      }, 300);

      // Max duration safeguard
      timerRef.current = setTimeout(() => {
        if (recorder.state === 'recording') {
          stopRecording();
        }
      }, maxDurationSeconds * 1000);
    } catch (err: any) {
      isRecordingRef.current = false;
      cleanupAudio();
      clearTimers();
      setIsRecording(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setPermissionState('denied');
      } else {
        setPermissionState('unavailable');
      }
      onError?.(err);
    }
  }, [
    isSupported,
    cleanupAudio,
    clearTimers,
    setupAudioMeter,
    lang,
    autoStopOnSilence,
    silenceTimeoutSeconds,
    stopRecording,
    maxDurationSeconds,
    onRecordingComplete,
    onError,
  ]);

  const cancelRecording = useCallback(() => {
    isRecordingRef.current = false;
    clearTimers();
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.onstop = null;
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }
    chunksRef.current = [];
    transcriptRef.current = '';
    cleanupAudio();
    setIsRecording(false);
    setLiveTranscript('');
    setRecordingDuration(0);
  }, [clearTimers, cleanupAudio]);

  // Privacy tab switch cleanup
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && isRecordingRef.current) {
        cancelRecording();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      cancelRecording();
    };
  }, [cancelRecording]);

  return {
    isRecording,
    isSupported,
    permissionState,
    recordingDuration,
    audioLevel,
    liveTranscript,
    startRecording,
    stopRecording,
    cancelRecording,
  };
}
