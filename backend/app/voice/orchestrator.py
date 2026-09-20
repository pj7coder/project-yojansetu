"""
YojanSetu - Day 27: Voice Conversation Orchestrator.

Coordinates inbound citizen voice turns and outbound speech responses:
1. Enforces single active voice turn per session (per-session lock / semaphore).
2. Verifies turn idempotency and conversation version conflict guards.
3. Invokes Day 23 AudioProcessingPipeline (Audio normalization & Silero VAD).
4. Invokes Day 22 Selected STT (Whisper tiny INT8 CPU with Devanagari prompt).
5. Dispatches transcript strictly to Day 25 ConversationManager.
6. Invokes Day 26 SpeechSynthesisService (MMS-TTS / Piper / Mock) via ConversationSpeechPolicy.
7. Manages ephemeral response audio lifecycle (VoiceResponseStore).
8. Enforces half-duplex rules and seamless graceful degradation to text.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.audio.config import get_audio_settings
from app.audio.pipeline import AudioProcessingPipeline
from app.audio.schemas import AudioErrorCode, AudioProcessingStatus, ProcessedAudioResult
from app.audio.temp_storage import get_temp_storage_manager
from app.audio.transcription import get_selected_stt_provider
from app.config.voice import get_voice_settings
from app.conversation.manager import ConversationManager, get_conversation_manager
from app.conversation.schemas import (
    ConversationInput,
    ConversationInputType,
    ConversationResponse,
)
from app.sessions.manager import CitizenSessionManager, SessionNotFoundError, get_session_manager
from app.sessions.models import CitizenSession
from app.stt.interface import SpeechToTextProvider
from app.tts.schemas import TTSResult
from app.tts.service import SpeechSynthesisService, get_speech_synthesis_service
from app.voice.errors import (
    ConversationConflictError,
    NoSpeechDetectedError,
    STTEmptyResultError,
    VoiceError,
    VoiceTurnActiveError,
)
from app.voice.metrics import get_voice_metrics
from app.voice.response_store import VoiceResponseStore, get_voice_response_store
from app.voice.schemas import (
    VoiceAudioDescriptor,
    VoiceErrorCode,
    VoiceRecoveryAction,
    VoiceReplayResponse,
    VoiceStatusResponse,
    VoiceTranscription,
    VoiceTurnResult,
    VoiceTurnTimings,
)
from app.voice.states import VoiceStateMachine, VoiceTransportState

logger = logging.getLogger(__name__)


class VoiceConversationOrchestrator:
    """
    Authoritative coordinator for the Day 27 Offline Voice Loop.
    Voice is strictly a voice rendering and transcription transport layer,
    never an intelligence or business logic layer.
    """

    def __init__(
        self,
        session_manager: Optional[CitizenSessionManager] = None,
        conversation_manager: Optional[ConversationManager] = None,
        audio_pipeline: Optional[AudioProcessingPipeline] = None,
        stt_provider: Optional[SpeechToTextProvider] = None,
        tts_service: Optional[SpeechSynthesisService] = None,
        response_store: Optional[VoiceResponseStore] = None,
    ):
        self.settings = get_voice_settings()
        self.session_mgr = session_manager or get_session_manager()
        self.conversation_mgr = conversation_manager or get_conversation_manager()
        self.audio_pipeline = audio_pipeline or AudioProcessingPipeline()
        self._stt_provider = stt_provider
        self.tts_service = tts_service or get_speech_synthesis_service()
        self.response_store = response_store or get_voice_response_store()
        self.temp_storage = get_temp_storage_manager()
        self.metrics = get_voice_metrics()

        # Per-session concurrency locks to guarantee exactly one active voice turn per citizen
        self._session_locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @property
    def stt(self) -> SpeechToTextProvider:
        if self._stt_provider is None:
            self._stt_provider = get_selected_stt_provider()
        return self._stt_provider

    def _get_session_lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]

    async def execute_voice_turn(
        self,
        session_id: str,
        audio_input: Union[str, Path, bytes],
        voice_turn_id: str,
        conversation_version: Optional[int] = None,
        filename_hint: str = "voice_turn.webm",
        db_session: Optional[Session] = None,
    ) -> VoiceTurnResult:
        """
        Executes a single conversational voice turn:
        Audio -> VAD -> STT -> Day 25 ConversationManager -> Day 26 TTS -> Playback Metadata.
        """
        t_total_start = time.perf_counter()
        timings = VoiceTurnTimings()

        # 1. Session validation
        session: CitizenSession = self.session_mgr.require_session(session_id)

        # 2. Acquire per-session lock (prevent overlapping voice turns)
        session_lock = self._get_session_lock(session_id)
        acquired = session_lock.acquire(blocking=False)
        if not acquired:
            logger.warning(f"Voice turn rejected: session '{session_id}' already has an active turn in flight")
            self.metrics.record_turn(error_type="CONFLICT")
            raise VoiceTurnActiveError()

        close_db_after = False
        if db_session is None:
            db_session = SessionLocal()
            close_db_after = True

        temp_audio_files: List[Path] = []
        try:
            session.voice_turn_active = True
            session.voice_mode_enabled = True

            # 3. Turn Idempotency Check
            if voice_turn_id in session.processed_turn_ids:
                logger.info(f"Idempotent voice turn replay detected for turn '{voice_turn_id}'")
                curr_resp = self.conversation_mgr.get_current_state(session_id, db_session=db_session)
                return VoiceTurnResult(
                    session_id=session_id,
                    voice_turn_id=voice_turn_id,
                    voice_state=VoiceTransportState.READY,
                    conversation=curr_resp,
                    warning="IDEMPOTENT_RETRY",
                    timings_ms=timings,
                )

            # 4. Conversation Version Conflict Check
            if conversation_version is not None and conversation_version != session.conversation_version:
                logger.warning(
                    f"Voice turn conflict: client version {conversation_version} "
                    f"!= current session version {session.conversation_version}"
                )
                self.metrics.record_turn(error_type="CONFLICT")
                raise ConversationConflictError()

            # 5. Audio Pipeline: Validation -> Normalization -> Silero VAD
            t_vad_start = time.perf_counter()
            processed_audio: ProcessedAudioResult = self.audio_pipeline.process(
                audio_input=audio_input,
                filename_hint=filename_hint,
                slice_audio_files=True,
            )
            timings.vad_ms = round((time.perf_counter() - t_vad_start) * 1000, 2)
            timings.normalization_ms = round(processed_audio.processing_time_ms, 2)

            if processed_audio.normalized_audio_path:
                temp_audio_files.append(Path(processed_audio.normalized_audio_path))
            for seg in processed_audio.segments:
                if seg.audio_path:
                    temp_audio_files.append(Path(seg.audio_path))

            # Handle Audio Validation Failures
            if processed_audio.status == AudioProcessingStatus.INVALID_AUDIO:
                logger.warning(f"Invalid audio uploaded: {processed_audio.error_message}")
                curr_resp = self.conversation_mgr.get_current_state(session_id, db_session=db_session)
                return VoiceTurnResult(
                    session_id=session_id,
                    voice_turn_id=voice_turn_id,
                    voice_state=VoiceTransportState.READY,
                    conversation=curr_resp,
                    error_code=VoiceErrorCode.INVALID_AUDIO,
                    recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
                    warning=processed_audio.error_message or "Invalid audio format",
                    timings_ms=timings,
                )

            # Handle No Speech Detected
            if processed_audio.status == AudioProcessingStatus.NO_SPEECH_DETECTED or not processed_audio.segments:
                logger.info(f"VAD detected no speech in voice turn '{voice_turn_id}' for session '{session_id}'")
                self.metrics.record_turn(vad_ms=timings.vad_ms, error_type="NO_SPEECH")
                session.last_voice_error = VoiceErrorCode.NO_SPEECH_DETECTED.value

                # Conversation state is strictly PRESERVED (turn not consumed)
                curr_resp = self.conversation_mgr.get_current_state(session_id, db_session=db_session)
                return VoiceTurnResult(
                    session_id=session_id,
                    voice_turn_id=voice_turn_id,
                    voice_state=VoiceTransportState.READY,
                    conversation=curr_resp,
                    error_code=VoiceErrorCode.NO_SPEECH_DETECTED,
                    recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
                    warning="मुझे आपकी आवाज़ सुनाई नहीं दी। कृपया दोबारा बोलें।",
                    timings_ms=timings,
                )

            # 6. Speech-to-Text Transcription via Selected Provider
            t_stt_start = time.perf_counter()
            transcript_parts = []
            for seg in processed_audio.segments:
                if seg.audio_path:
                    seg_res = self.stt.transcribe(Path(seg.audio_path), language_hint="hi")
                    if seg_res.text and seg_res.text.strip():
                        transcript_parts.append(seg_res.text.strip())

            raw_transcript = " ".join(transcript_parts).strip()
            timings.stt_ms = round((time.perf_counter() - t_stt_start) * 1000, 2)

            # Handle Empty STT Result
            if not raw_transcript:
                logger.info(f"STT produced empty transcript for voice turn '{voice_turn_id}'")
                self.metrics.record_turn(vad_ms=timings.vad_ms, stt_ms=timings.stt_ms, error_type="STT_EMPTY")
                session.last_voice_error = VoiceErrorCode.STT_EMPTY_RESULT.value

                curr_resp = self.conversation_mgr.get_current_state(session_id, db_session=db_session)
                return VoiceTurnResult(
                    session_id=session_id,
                    voice_turn_id=voice_turn_id,
                    voice_state=VoiceTransportState.READY,
                    conversation=curr_resp,
                    error_code=VoiceErrorCode.STT_EMPTY_RESULT,
                    recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
                    warning="मुझे आपकी बात स्पष्ट रूप से समझ नहीं आई। कृपया फिर से बोलें।",
                    timings_ms=timings,
                )

            # 7. Day 25 ConversationManager Turn Dispatch
            t_conv_start = time.perf_counter()
            conv_input = ConversationInput(
                type=ConversationInputType.STT_TRANSCRIPT,
                text=raw_transcript,
                client_turn_id=voice_turn_id,
                conversation_version=session.conversation_version,
                language=session.preferred_language,
            )
            conv_response: ConversationResponse = self.conversation_mgr.handle_input(
                session_id=session_id,
                inp=conv_input,
                db_session=db_session,
            )
            timings.conversation_ms = round((time.perf_counter() - t_conv_start) * 1000, 2)

            # 8. Day 26 Speech Synthesis of Structured Response
            t_tts_start = time.perf_counter()
            audio_descriptor: Optional[VoiceAudioDescriptor] = None
            tts_warning: Optional[str] = None
            voice_state = VoiceTransportState.SPEAKING

            try:
                tts_result: TTSResult = await self.tts_service.synthesize_conversation_response(
                    response=conv_response,
                    preferred_language=session.preferred_language,
                )
                timings.tts_ms = round((time.perf_counter() - t_tts_start) * 1000, 2)

                # Store ephemeral synthesized audio in VoiceResponseStore
                resp_token = self.response_store.store_response(
                    session_id=session_id,
                    conversation_version=conv_response.meta.version,
                    audio_path=Path(tts_result.audio_path),
                    duration_ms=tts_result.duration_ms,
                    sample_rate=tts_result.sample_rate,
                    is_cached_generic=tts_result.cached,
                )
                session.last_voice_response_id = resp_token

                audio_descriptor = VoiceAudioDescriptor(
                    response_id=resp_token,
                    format="wav",
                    duration_ms=tts_result.duration_ms,
                    sample_rate=tts_result.sample_rate,
                    audio_url=f"/api/v1/citizen/sessions/{session_id}/voice/responses/{resp_token}/audio",
                    cached=tts_result.cached,
                )
            except Exception as tts_exc:
                # Rule 51: If TTS fails, conversation state HAS advanced!
                # Do NOT roll back valid semantic turn. Return text + warning.
                logger.error(f"TTS synthesis failed on turn '{voice_turn_id}': {tts_exc}", exc_info=True)
                tts_warning = f"{VoiceErrorCode.TTS_UNAVAILABLE.value}: Audio synthesis failed. Continuing in text mode."
                voice_state = VoiceTransportState.READY
                self.metrics.record_turn(
                    vad_ms=timings.vad_ms,
                    stt_ms=timings.stt_ms,
                    conv_ms=timings.conversation_ms,
                    error_type="TTS_FAILURE",
                )

            timings.total_processing_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
            self.metrics.record_turn(
                vad_ms=timings.vad_ms,
                stt_ms=timings.stt_ms,
                conv_ms=timings.conversation_ms,
                tts_ms=timings.tts_ms,
                total_ms=timings.total_processing_ms,
            )

            return VoiceTurnResult(
                session_id=session_id,
                voice_turn_id=voice_turn_id,
                voice_state=voice_state,
                conversation=conv_response,
                transcription=VoiceTranscription(
                    text=raw_transcript,
                    stt_provider=getattr(self.stt, "provider_id", getattr(self.stt, "name", "whisper")),
                    latency_ms=timings.stt_ms,
                ),
                audio=audio_descriptor,
                warning=tts_warning,
                timings_ms=timings,
            )

        finally:
            # Privacy guarantee: Always delete uploaded citizen audio files
            for p in temp_audio_files:
                self.temp_storage.cleanup_file(p)

            if close_db_after and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass

            session.voice_turn_active = False
            session_lock.release()

    async def replay_last_response(
        self,
        session_id: str,
        db_session: Optional[Session] = None,
    ) -> VoiceReplayResponse:
        """
        Re-synthesizes the current conversation response without mutating profile facts or turns.
        """
        close_db_after = False
        if db_session is None:
            db_session = SessionLocal()
            close_db_after = True

        try:
            session: CitizenSession = self.session_mgr.require_session(session_id)
            curr_resp: ConversationResponse = self.conversation_mgr.get_current_state(session_id, db_session=db_session)

            # Synthesize audio
            tts_result: TTSResult = await self.tts_service.synthesize_conversation_response(
                response=curr_resp,
                preferred_language=session.preferred_language,
            )

            resp_token = self.response_store.store_response(
                session_id=session_id,
                conversation_version=curr_resp.meta.version,
                audio_path=Path(tts_result.audio_path),
                duration_ms=tts_result.duration_ms,
                sample_rate=tts_result.sample_rate,
                is_cached_generic=tts_result.cached,
            )
            session.last_voice_response_id = resp_token
            self.metrics.replays_served += 1

            return VoiceReplayResponse(
                session_id=session_id,
                voice_state=VoiceTransportState.SPEAKING,
                audio=VoiceAudioDescriptor(
                    response_id=resp_token,
                    format="wav",
                    duration_ms=tts_result.duration_ms,
                    sample_rate=tts_result.sample_rate,
                    audio_url=f"/api/v1/citizen/sessions/{session_id}/voice/responses/{resp_token}/audio",
                    cached=tts_result.cached,
                ),
                speech_text=curr_resp.message.text_hi if session.preferred_language == "hi" else curr_resp.message.text_en,
                conversation_version=curr_resp.meta.version,
            )
        finally:
            if close_db_after and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass

    def get_voice_status(self, session_id: str) -> VoiceStatusResponse:
        """Returns component readiness and active state for citizen voice mode."""
        session = self.session_mgr.get_session(session_id)
        vad_prov = self.audio_pipeline.vad
        stt_prov = self.stt
        tts_prov = self.tts_service.registry.get_provider()

        return VoiceStatusResponse(
            voice_enabled=self.settings.voice_enabled,
            current_transport_state=(
                VoiceTransportState.SPEAKING
                if session and session.last_voice_response_id
                else VoiceTransportState.READY
            ),
            vad_available=vad_prov.is_available() if vad_prov else False,
            stt_available=stt_prov.is_available() if stt_prov else False,
            stt_provider=getattr(stt_prov, "provider_id", getattr(stt_prov, "name", "whisper")) if stt_prov else "unknown",
            stt_model=getattr(stt_prov, "model_name", "unknown"),
            tts_available=tts_prov.is_available() if tts_prov else False,
            tts_provider=tts_prov.name if tts_prov else "unknown",
            tts_model=tts_prov.model_name if tts_prov else "unknown",
            active_turn=session.voice_turn_active if session else False,
            conversation_version=session.conversation_version if session else 1,
            pipeline_version=self.settings.voice_pipeline_version,
        )


_orchestrator_instance: Optional[VoiceConversationOrchestrator] = None


def get_voice_orchestrator() -> VoiceConversationOrchestrator:
    """Returns singleton VoiceConversationOrchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = VoiceConversationOrchestrator()
    return _orchestrator_instance
