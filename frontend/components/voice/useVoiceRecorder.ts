'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

export type MicPermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

interface UseVoiceRecorderOptions {
  maxDurationSeconds?: number;
  lang?: 'hi' | 'en';
  onRecordingComplete: (audioBlob: Blob, transcript?: string) => void;
  onError?: (error: Error) => void;
}

export function useVoiceRecorder({
  maxDurationSeconds = 60,
  lang = 'hi',
  onRecordingComplete,
  onError,
}: UseVoiceRecorderOptions) {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [permissionState, setPermissionState] = useState<MicPermissionState>('prompt');
  const [recordingDuration, setRecordingDuration] = useState<number>(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef<string>('');
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const durationTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Check browser support
  const isSupported = typeof window !== 'undefined' && !!navigator?.mediaDevices?.getUserMedia;

  // Cleanup active audio tracks
  const cleanupStream = useCallback(() => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  // Clear timers
  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
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

  const startRecording = useCallback(async () => {
    if (!isSupported) {
      setPermissionState('unavailable');
      onError?.(new Error('Browser does not support audio recording.'));
      return;
    }

    try {
      cleanupStream();
      chunksRef.current = [];
      transcriptRef.current = '';
      setRecordingDuration(0);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      mediaStreamRef.current = stream;
      setPermissionState('granted');

      // Initialize browser SpeechRecognition if available for instant live transcription
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
            transcriptRef.current = fullText.trim();
          };

          recognition.onerror = (e: any) => {
            console.warn('SpeechRecognition notice:', e.error);
          };

          recognition.start();
          recognitionRef.current = recognition;
        } catch (recErr) {
          console.warn('SpeechRecognition failed to start:', recErr);
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
        cleanupStream();
        clearTimers();
        setIsRecording(false);
        if (fullBlob.size > 0) {
          onRecordingComplete(fullBlob, finalTranscript);
        }
      };

      recorder.start(250); // Collect in 250ms chunks
      setIsRecording(true);

      // Duration counter
      const startTime = Date.now();
      durationTimerRef.current = setInterval(() => {
        setRecordingDuration(Math.round((Date.now() - startTime) / 1000));
      }, 500);

      // Max recording duration safeguard
      timerRef.current = setTimeout(() => {
        if (recorder.state === 'recording') {
          recorder.stop();
        }
      }, maxDurationSeconds * 1000);
    } catch (err: any) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
        recognitionRef.current = null;
      }
      cleanupStream();
      clearTimers();
      setIsRecording(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setPermissionState('denied');
      } else {
        setPermissionState('unavailable');
      }
      onError?.(err);
    }
  }, [isSupported, lang, maxDurationSeconds, onRecordingComplete, onError, cleanupStream, clearTimers]);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const cancelRecording = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.onstop = null; // Do not trigger callback
      mediaRecorderRef.current.stop();
    }
    chunksRef.current = [];
    transcriptRef.current = '';
    cleanupStream();
    clearTimers();
    setIsRecording(false);
    setRecordingDuration(0);
  }, [cleanupStream, clearTimers]);

  // Privacy cleanup on unmount or tab hidden
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && isRecording) {
        cancelRecording();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      cancelRecording();
    };
  }, [isRecording, cancelRecording]);

  return {
    isRecording,
    isSupported,
    permissionState,
    recordingDuration,
    startRecording,
    stopRecording,
    cancelRecording,
  };
}
