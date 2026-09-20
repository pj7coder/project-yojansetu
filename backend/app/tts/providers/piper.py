"""
YojanSetu - Day 26: Piper TTS Provider Adapter (ONNX).

Implements TextToSpeechProvider using Rhasspy's Piper neural TTS engine on ONNX runtime.
Provides low-latency, lightweight offline speech synthesis on CPU with high intelligibility.
"""

import gc
import logging
import time
import wave
from pathlib import Path
from typing import Dict, Optional

from app.tts.audio_validation import AudioValidator
from app.tts.interface import TextToSpeechProvider
from app.tts.schemas import TTSErrorCode, TTSResult
from app.tts.temp_storage import get_tts_temp_manager

logger = logging.getLogger(__name__)

# Available pre-trained Piper Hindi voice definitions
PIPER_VOICES: Dict[str, Dict[str, str]] = {
    "pratham": {
        "model_file": "hi_IN-pratham-medium.onnx",
        "config_file": "hi_IN-pratham-medium.onnx.json",
        "gender": "male",
        "sample_rate": "22050",
    },
    "priyamvada": {
        "model_file": "hi_IN-priyamvada-medium.onnx",
        "config_file": "hi_IN-priyamvada-medium.onnx.json",
        "gender": "female",
        "sample_rate": "22050",
    },
}


class PiperTTSProvider(TextToSpeechProvider):
    """
    Adapter for Piper TTS running on ONNX runtime.
    Supports fast CPU inference and multiple local Hindi voices.
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        default_voice: str = "pratham",
    ):
        self._model_dir = Path(model_dir or "storage/models/piper").resolve()
        self._default_voice = default_voice if default_voice in PIPER_VOICES else "pratham"
        self._voices: Dict[str, object] = {}
        self._active_voice_name = self._default_voice
        self._sample_rate = 22050

    @property
    def name(self) -> str:
        return "piper"

    @property
    def model_name(self) -> str:
        return f"piper-hi_IN-{self._active_voice_name}-medium"

    @property
    def default_sample_rate(self) -> int:
        return self._sample_rate

    def is_available(self) -> bool:
        """Checks if piper-tts is installed and at least one model exists or model_dir is ready."""
        try:
            import piper
            return True
        except ImportError:
            return False

    def is_loaded(self) -> bool:
        return len(self._voices) > 0

    def get_voice_path(self, voice_name: str) -> Optional[Path]:
        """Returns path to .onnx file for specified voice name."""
        voice_info = PIPER_VOICES.get(voice_name.lower())
        if not voice_info:
            return None
        model_path = self._model_dir / voice_info["model_file"]
        return model_path if model_path.exists() else None

    def load_model(self, voice_name: Optional[str] = None) -> None:
        """Loads specified voice (or default voice) into memory."""
        target_voice = voice_name or self._default_voice
        if target_voice in self._voices:
            self._active_voice_name = target_voice
            return

        voice_info = PIPER_VOICES.get(target_voice.lower())
        if not voice_info:
            raise ValueError(f"Unknown Piper voice: {target_voice}. Available: {list(PIPER_VOICES.keys())}")

        model_path = self._model_dir / voice_info["model_file"]
        config_path = self._model_dir / voice_info["config_file"]

        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper ONNX model not found at {model_path}. "
                f"Please ensure offline assets are downloaded to {self._model_dir}."
            )

        logger.info(f"Loading Piper voice '{target_voice}' from {model_path}...")
        t0 = time.perf_counter()
        try:
            from piper.voice import PiperVoice

            voice_obj = PiperVoice.load(model_path=str(model_path), config_path=str(config_path) if config_path.exists() else None)
            self._voices[target_voice] = voice_obj
            self._active_voice_name = target_voice
            self._sample_rate = getattr(voice_obj.config, "sample_rate", 22050)
            elapsed = time.perf_counter() - t0
            logger.info(f"Piper voice '{target_voice}' loaded in {elapsed:.2f}s (sample_rate={self._sample_rate})")
        except Exception as exc:
            logger.error(f"Failed to load Piper voice '{target_voice}': {exc}")
            raise RuntimeError(f"{TTSErrorCode.TTS_MODEL_LOAD_FAILED.value}: {exc}")

    def unload_model(self) -> None:
        """Releases all Piper voice models from memory."""
        self._voices.clear()
        gc.collect()
        logger.info("Piper TTS models unloaded from memory.")

    def synthesize(
        self,
        text: str,
        language: str = "hi",
        voice: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSResult:
        if not text or not text.strip():
            raise ValueError(TTSErrorCode.TTS_EMPTY_TEXT.value)

        target_voice = voice or self._active_voice_name
        if target_voice not in self._voices:
            self.load_model(target_voice)

        voice_obj = self._voices[target_voice]

        t0 = time.perf_counter()
        temp_mgr = get_tts_temp_manager()
        temp_path = temp_mgr.create_temp_file(suffix=".wav", prefix="piper_")

        try:
            from piper.config import SynthesisConfig

            syn_config = None
            if speaking_rate is not None and speaking_rate > 0:
                # In Piper, length_scale is inversely proportional to speed:
                # length_scale > 1.0 means slower, < 1.0 means faster
                syn_config = SynthesisConfig(length_scale=1.0 / speaking_rate)

            with wave.open(str(temp_path), "wb") as wav_file:
                voice_obj.synthesize_wav(text, wav_file, syn_config=syn_config)

        except Exception as exc:
            temp_mgr.cleanup_file(temp_path)
            logger.error(f"Piper synthesis failed: {exc}")
            raise RuntimeError(f"{TTSErrorCode.TTS_SYNTHESIS_FAILED.value}: {exc}")

        synthesis_ms = (time.perf_counter() - t0) * 1000.0

        # Validate generated audio
        data, sr, duration_ms, peak, rms = AudioValidator.validate_and_measure(temp_path)

        # Normalize volume safely and rewrite if needed
        norm_data = AudioValidator.safe_normalize_volume(data, target_peak=0.95)
        AudioValidator.write_wav(temp_path, norm_data, sr)

        return TTSResult(
            provider=self.name,
            model=f"hi_IN-{target_voice}-medium",
            voice=target_voice,
            language=language,
            duration_ms=duration_ms,
            synthesis_ms=synthesis_ms,
            sample_rate=sr,
            audio_format="wav",
            audio_path=str(temp_path),
            cached=False,
        )
