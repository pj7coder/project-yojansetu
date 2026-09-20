"""
JanSetu - Day 27: Voice Loop Exception Hierarchy.
"""

from typing import Optional
from app.voice.schemas import VoiceErrorCode, VoiceRecoveryAction


class VoiceError(Exception):
    """Base exception for voice subsystem errors."""
    def __init__(
        self,
        message: str,
        error_code: VoiceErrorCode,
        recovery_action: VoiceRecoveryAction = VoiceRecoveryAction.RETRY_SAME_TURN,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.recovery_action = recovery_action


class VoiceTurnActiveError(VoiceError):
    """Raised when a concurrent voice turn is attempted on an active session."""
    def __init__(self, message: str = "A voice turn is already active for this session."):
        super().__init__(
            message=message,
            error_code=VoiceErrorCode.VOICE_TURN_ALREADY_ACTIVE,
            recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
        )


class ConversationConflictError(VoiceError):
    """Raised when the submitted voice turn's conversation version is stale."""
    def __init__(self, message: str = "Conversation state has changed. Please repeat your response."):
        super().__init__(
            message=message,
            error_code=VoiceErrorCode.CONVERSATION_STATE_CONFLICT,
            recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
        )


class NoSpeechDetectedError(VoiceError):
    """Raised when VAD detects no usable speech in the captured audio."""
    def __init__(self, message: str = "मुझे आपकी आवाज़ सुनाई नहीं दी। कृपया दोबारा बोलें।"):
        super().__init__(
            message=message,
            error_code=VoiceErrorCode.NO_SPEECH_DETECTED,
            recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
        )


class STTEmptyResultError(VoiceError):
    """Raised when STT engine produces an empty or whitespace transcript."""
    def __init__(self, message: str = "मुझे आपकी बात स्पष्ट रूप से समझ नहीं आई। कृपया फिर से बोलें।"):
        super().__init__(
            message=message,
            error_code=VoiceErrorCode.STT_EMPTY_RESULT,
            recovery_action=VoiceRecoveryAction.RETRY_SAME_TURN,
        )
