"""
JanSetu - Day 22: STT Providers Package.
"""

from app.stt.providers.whisper import WhisperSTTProvider
from app.stt.providers.indic_asr import IndicASRSTTProvider
from app.stt.providers.mock import MockSTTProvider

__all__ = ["WhisperSTTProvider", "IndicASRSTTProvider", "MockSTTProvider"]
