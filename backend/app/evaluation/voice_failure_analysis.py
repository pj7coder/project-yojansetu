"""
YojanSetu - Day 32: Voice Failure Taxonomy and Earliest Root-Cause Attribution.

Provides structured root-cause attribution across all 6 voice stages:
1. VAD (Silero VAD speech detection)
2. STT (Speech-to-Text literal & semantic transcription)
3. Profile Extraction (Entity parsing & normalization)
4. Confirmation (Safety triggers & contextual confirmation)
5. Conversation Manager (Deterministic state machine)
6. TTS (SpeechTextNormalizer & audio generation)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VoicePipelineStage(str, Enum):
    VAD = "VAD"
    STT = "STT"
    PROFILE_EXTRACTION = "PROFILE_EXTRACTION"
    CONFIRMATION = "CONFIRMATION"
    CONVERSATION_MANAGER = "CONVERSATION_MANAGER"
    TTS = "TTS"
    SYSTEM = "SYSTEM"


class VoiceFailureCode(str, Enum):
    VAD_MISSED_SPEECH = "VAD_MISSED_SPEECH"
    VAD_CLIPPED_AUDIO = "VAD_CLIPPED_AUDIO"
    VAD_FALSE_POSITIVE = "VAD_FALSE_POSITIVE"

    STT_WRONG_NUMBER = "STT_WRONG_NUMBER"
    STT_WRONG_DISTRICT = "STT_WRONG_DISTRICT"
    STT_NEGATION_ERROR = "STT_NEGATION_ERROR"
    STT_TRANSCRIPTION_MISMATCH = "STT_TRANSCRIPTION_MISMATCH"

    PROFILE_EXTRACTION_ERROR = "PROFILE_EXTRACTION_ERROR"
    NUMBER_NORMALIZATION_ERROR = "NUMBER_NORMALIZATION_ERROR"
    FALSE_PROFILE_INFERENCE = "FALSE_PROFILE_INFERENCE"

    CONFIRMATION_SKIPPED = "CONFIRMATION_SKIPPED"
    CONFIRMATION_CONTEXT_ERROR = "CONFIRMATION_CONTEXT_ERROR"

    CONVERSATION_STATE_ERROR = "CONVERSATION_STATE_ERROR"
    QUESTION_SELECTION_ERROR = "QUESTION_SELECTION_ERROR"

    TTS_NUMERIC_PRONUNCIATION_ERROR = "TTS_NUMERIC_PRONUNCIATION_ERROR"
    TTS_NEGATION_ERROR = "TTS_NEGATION_ERROR"

    VOICE_PIPELINE_TIMEOUT = "VOICE_PIPELINE_TIMEOUT"
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"


class VoiceFailureItem(BaseModel):
    case_id: str
    stage: VoicePipelineStage
    code: VoiceFailureCode
    severity: str = "MAJOR"  # CRITICAL, MAJOR, MINOR
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class VoiceFailureAttributor:
    """
    Attributes voice system failures to the earliest failing stage in the pipeline.
    Prevents downstream components (e.g. Profile or Conversation) from being blamed
    for upstream errors (e.g. VAD clipping or STT mis-transcription).
    """

    @classmethod
    def diagnose_voice_case(
        cls,
        case_id: str,
        contains_speech_expected: bool,
        contains_speech_actual: bool,
        hypothesis_transcript: str,
        reference_transcript: str,
        expected_field: Optional[str] = None,
        extracted_field: Optional[str] = None,
        expected_value: Any = None,
        extracted_value: Any = None,
        confirmation_required: bool = False,
        confirmation_triggered: bool = False,
        expected_state: Optional[str] = None,
        actual_state: Optional[str] = None,
        expected_action: Optional[str] = None,
        actual_action: Optional[str] = None,
        unsupported_inferences: Optional[List[str]] = None,
        stt_semantic_error: Optional[str] = None,
    ) -> List[VoiceFailureItem]:
        failures: List[VoiceFailureItem] = []

        # 1. Stage 1: VAD Checks
        if contains_speech_expected and not contains_speech_actual:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.VAD,
                    code=VoiceFailureCode.VAD_MISSED_SPEECH,
                    severity="CRITICAL",
                    description="VAD failed to detect speech in an active audio segment.",
                    evidence={"contains_speech_expected": True, "contains_speech_actual": False},
                )
            )
            return failures

        if not contains_speech_expected and contains_speech_actual:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.VAD,
                    code=VoiceFailureCode.VAD_FALSE_POSITIVE,
                    severity="MAJOR",
                    description="VAD detected speech on silence or pure background noise.",
                    evidence={"contains_speech_expected": False, "contains_speech_actual": True},
                )
            )
            return failures

        if not contains_speech_expected and not contains_speech_actual:
            # Clean silence case handled properly
            return failures

        # 2. Stage 2: STT Checks
        if stt_semantic_error == "STT_WRONG_NUMBER":
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.STT,
                    code=VoiceFailureCode.STT_WRONG_NUMBER,
                    severity="CRITICAL",
                    description="STT transcribed an incorrect numeric value (e.g. 62 -> 26).",
                    evidence={"hypothesis": hypothesis_transcript, "reference": reference_transcript},
                )
            )
            return failures

        if stt_semantic_error == "STT_WRONG_DISTRICT":
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.STT,
                    code=VoiceFailureCode.STT_WRONG_DISTRICT,
                    severity="CRITICAL",
                    description="STT failed to recognize or substituted a Rajasthan district entity.",
                    evidence={"hypothesis": hypothesis_transcript, "reference": reference_transcript},
                )
            )
            return failures

        if stt_semantic_error == "STT_NEGATION_ERROR":
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.STT,
                    code=VoiceFailureCode.STT_NEGATION_ERROR,
                    severity="CRITICAL",
                    description="STT dropped or hallucinated a negation token ('नहीं').",
                    evidence={"hypothesis": hypothesis_transcript, "reference": reference_transcript},
                )
            )
            return failures

        # 3. Stage 3: Profile Extraction Checks
        if unsupported_inferences:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.PROFILE_EXTRACTION,
                    code=VoiceFailureCode.FALSE_PROFILE_INFERENCE,
                    severity="CRITICAL",
                    description=f"Profile extractor made ungrounded critical inference: {unsupported_inferences}",
                    evidence={"unsupported_inferences": unsupported_inferences},
                )
            )
            return failures

        if expected_field and extracted_field != expected_field:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.PROFILE_EXTRACTION,
                    code=VoiceFailureCode.PROFILE_EXTRACTION_ERROR,
                    severity="MAJOR",
                    description=f"Expected field '{expected_field}' not detected (got '{extracted_field}').",
                    evidence={"expected_field": expected_field, "extracted_field": extracted_field},
                )
            )
            return failures

        if expected_value is not None and extracted_value != expected_value:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.PROFILE_EXTRACTION,
                    code=VoiceFailureCode.NUMBER_NORMALIZATION_ERROR,
                    severity="MAJOR",
                    description=f"Normalized value mismatch for '{expected_field}': expected {expected_value}, got {extracted_value}.",
                    evidence={"expected_value": expected_value, "extracted_value": extracted_value},
                )
            )
            return failures

        # 4. Stage 4: Confirmation Checks
        if confirmation_required and not confirmation_triggered:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.CONFIRMATION,
                    code=VoiceFailureCode.CONFIRMATION_SKIPPED,
                    severity="CRITICAL",
                    description=f"Critical field '{expected_field}' mutated state without mandatory confirmation.",
                    evidence={"field": expected_field, "value": extracted_value},
                )
            )
            return failures

        # 5. Stage 5: Conversation State Checks
        if expected_state and actual_state and expected_state != actual_state:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.CONVERSATION_MANAGER,
                    code=VoiceFailureCode.CONVERSATION_STATE_ERROR,
                    severity="MAJOR",
                    description=f"Conversation transitioned to state '{actual_state}', expected '{expected_state}'.",
                    evidence={"expected_state": expected_state, "actual_state": actual_state},
                )
            )
            return failures

        if expected_action and actual_action and expected_action != actual_action:
            failures.append(
                VoiceFailureItem(
                    case_id=case_id,
                    stage=VoicePipelineStage.CONVERSATION_MANAGER,
                    code=VoiceFailureCode.QUESTION_SELECTION_ERROR,
                    severity="MAJOR",
                    description=f"Conversation action was '{actual_action}', expected '{expected_action}'.",
                    evidence={"expected_action": expected_action, "actual_action": actual_action},
                )
            )
            return failures

        return failures
