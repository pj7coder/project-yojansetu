import { ConversationTurnResponse } from './citizen';

export type VoiceTransportState =
  | 'IDLE'
  | 'READY'
  | 'LISTENING'
  | 'SPEECH_DETECTED'
  | 'WAITING_FOR_END_OF_SPEECH'
  | 'PROCESSING_AUDIO'
  | 'TRANSCRIBING'
  | 'PROCESSING_TURN'
  | 'SYNTHESIZING'
  | 'SPEAKING'
  | 'RECOVERABLE_ERROR'
  | 'STOPPED';

export interface VoiceAudioDescriptor {
  response_id: string;
  format: string;
  duration_ms: number;
  sample_rate: number;
  audio_url: string;
  cached?: boolean;
}

export interface VoiceTranscription {
  text: string;
  confidence?: number;
  stt_provider: string;
  latency_ms: number;
}

export interface VoiceTurnTimings {
  audio_validation_ms: number;
  normalization_ms: number;
  vad_ms: number;
  stt_ms: number;
  conversation_ms: number;
  tts_ms: number;
  total_processing_ms: number;
}

export interface VoiceTurnResponse {
  session_id: string;
  voice_turn_id: string;
  voice_state: VoiceTransportState;
  conversation: ConversationTurnResponse;
  transcription?: VoiceTranscription;
  audio?: VoiceAudioDescriptor;
  warning?: string;
  error_code?: string;
  recovery_action?: string;
  timings_ms?: VoiceTurnTimings;
}

export interface VoiceReplayResponse {
  session_id: string;
  voice_state: VoiceTransportState;
  audio: VoiceAudioDescriptor;
  speech_text: string;
  conversation_version: number;
}

export interface VoiceStatusResponse {
  voice_enabled: boolean;
  current_transport_state: VoiceTransportState;
  vad_available: boolean;
  stt_available: boolean;
  stt_provider: string;
  stt_model: string;
  tts_available: boolean;
  tts_provider: string;
  tts_model: string;
  active_turn: boolean;
  conversation_version: number;
  pipeline_version: string;
}
