"""
JanSetu - Day 22: Speech-to-Text Benchmark Configuration.

Centralizes configuration parameters for dataset paths, model names,
devices, and evaluation flags. Does NOT hardcode system-specific paths.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class STTSettings(BaseSettings):
    """Configuration settings for STT benchmarking."""

    dataset_path: Path = Path("tests/stt_benchmark")
    storage_path: Path = Path("storage/benchmarks/stt")
    device: str = "cpu"  # "cpu" or "cuda"
    precision: str = "int8"  # "int8", "fp16", "fp32"
    whisper_model: str = "tiny"  # "tiny", "base", "small", "medium"
    indic_asr_model: str = "Harveenchadha/vakyansh-wav2vec2-hindi-him-4200"
    language_hint: Optional[str] = "hi"
    dataset_version: str = "1.0"
    benchmark_version: str = "1.0"
    batch_size: int = 1
    max_audio_duration_seconds: float = 300.0

    model_config = {
        "env_prefix": "STT_",
        "extra": "ignore",
    }


def get_stt_settings() -> STTSettings:
    """Returns singleton STTSettings instance."""
    return STTSettings()
