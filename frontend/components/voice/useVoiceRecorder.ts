'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

export type MicPermissionState = 'prompt' | 'granted' | 'denied' | 'unavailable';

interface UseVoiceRecorderOptions {
  maxDurationSeconds?: number;
  onRecordingComplete: (audioBlob: Blob) => void;
  onError?: (error: Error) => void;
}

export function useVoiceRecorder({
  maxDurationSeconds = 60,
  onRecordingComplete,
  onError,
}: UseVoiceRecorderOptions) {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [permissionState, setPermissionState] = useState<MicPermissionState>('prompt');
  const [recordingDuration, setRecordingDuration] = useState<number>(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
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

      const mimeType = getSupportedMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const fullBlob = new Blob(chunksRef.current, {
          type: mimeType || 'audio/webm',
        });
        chunksRef.current = [];
        cleanupStream();
        clearTimers();
        setIsRecording(false);
        if (fullBlob.size > 0) {
          onRecordingComplete(fullBlob);
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
  }, [isSupported, maxDurationSeconds, onRecordingComplete, onError, cleanupStream, clearTimers]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.onstop = null; // Do not trigger callback
      mediaRecorderRef.current.stop();
    }
    chunksRef.current = [];
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
