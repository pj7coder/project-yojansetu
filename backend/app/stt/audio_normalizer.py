"""
YojanSetu - Day 22: Audio Normalizer.

Standardizes all input audio formats (WAV, MP3, M4A, OGG, FLAC) into the
canonical baseline required for fair, reproducible STT evaluation:
- Container: WAV
- Channels: 1 (Mono)
- Sampling Rate: 16,000 Hz (16 kHz)
- Sample Format: 16-bit Linear PCM (signed 16-bit little-endian)

Uses PyAV / soundfile with safe path and size validation.
"""

from io import BytesIO
import logging
from pathlib import Path
from typing import Optional, Tuple
import wave

logger = logging.getLogger("yojansetu.stt.audio_normalizer")

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm"}
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit
MAX_AUDIO_DURATION_SECONDS = 300.0       # 5 minutes limit
CANONICAL_SAMPLE_RATE = 16000
CANONICAL_CHANNELS = 1


class AudioNormalizationError(Exception):
    """Raised when audio conversion or validation fails."""
    pass


class AudioNormalizer:
    """
    Normalizes audio files to 16kHz mono 16-bit PCM WAV.
    Provides safe file validation and input sanitization.
    """

    @classmethod
    def validate_file(cls, input_path: Path) -> None:
        """Validates existence, extension, and file size limits."""
        path = Path(input_path).resolve()
        if not path.is_file():
            raise AudioNormalizationError(f"Audio file does not exist: {input_path}")

        ext = path.suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise AudioNormalizationError(
                f"Unsupported audio format '{ext}'. Allowed extensions: {sorted(ALLOWED_AUDIO_EXTENSIONS)}"
            )

        file_size = path.stat().st_size
        if file_size == 0:
            raise AudioNormalizationError(f"Audio file is empty (0 bytes): {input_path}")
        if file_size > MAX_AUDIO_SIZE_BYTES:
            raise AudioNormalizationError(
                f"Audio file size ({file_size} bytes) exceeds maximum limit ({MAX_AUDIO_SIZE_BYTES} bytes)"
            )

    @classmethod
    def get_audio_info(cls, audio_path: Path) -> Tuple[float, int, int]:
        """
        Extracts duration in seconds, sample rate, and channels.
        Returns: (duration_seconds, sample_rate, channels)
        """
        cls.validate_file(audio_path)
        path = Path(audio_path).resolve()

        # Try wave module for simple WAV
        if path.suffix.lower() == ".wav":
            try:
                with wave.open(str(path), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    channels = wf.getnchannels()
                    duration = frames / float(rate) if rate > 0 else 0.0
                    return duration, rate, channels
            except Exception:
                pass

        # Try soundfile
        try:
            import soundfile as sf
            info = sf.info(str(path))
            return float(info.duration), int(info.samplerate), int(info.channels)
        except Exception:
            pass

        # Try PyAV
        try:
            import av
            with av.open(str(path)) as container:
                stream = container.streams.audio[0]
                rate = stream.rate or CANONICAL_SAMPLE_RATE
                channels = stream.channels or CANONICAL_CHANNELS
                duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
                return duration, rate, channels
        except Exception as e:
            raise AudioNormalizationError(f"Failed to inspect audio file {audio_path}: {e}")

    @classmethod
    def normalize_to_wav(
        cls,
        input_path: Path,
        output_path: Optional[Path] = None,
        overwrite: bool = True,
    ) -> Path:
        """
        Converts input audio file to canonical 16kHz mono 16-bit PCM WAV.
        If output_path is omitted, creates a normalized copy with '_16k.wav' suffix.
        """
        cls.validate_file(input_path)
        in_path = Path(input_path).resolve()

        if output_path:
            out_path = Path(output_path).resolve()
        else:
            out_path = in_path.with_name(f"{in_path.stem}_normalized_16k.wav")

        if out_path.exists() and not overwrite:
            return out_path

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Try PyAV (fast, handles all containers without ffmpeg CLI)
        try:
            import av
            with av.open(str(in_path)) as in_container:
                if not in_container.streams.audio:
                    raise AudioNormalizationError(f"No audio stream found in {in_path}")

                in_stream = in_container.streams.audio[0]
                resampler = av.AudioResampler(
                    format="s16",
                    layout="mono",
                    rate=CANONICAL_SAMPLE_RATE,
                )

                with av.open(str(out_path), mode="w", format="wav") as out_container:
                    out_stream = out_container.add_stream("pcm_s16le", rate=CANONICAL_SAMPLE_RATE)
                    out_stream.layout = "mono"

                    for frame in in_container.decode(in_stream):
                        resampled_frames = resampler.resample(frame)
                        for r_frame in resampled_frames:
                            for packet in out_stream.encode(r_frame):
                                out_container.mux(packet)

                    # Flush
                    for packet in out_stream.encode(None):
                        out_container.mux(packet)

            logger.debug(f"Normalized audio via PyAV: {in_path} -> {out_path}")
            return out_path

        except Exception as av_err:
            logger.debug(f"PyAV conversion failed ({av_err}), falling back to soundfile/numpy")

        # 2. Try soundfile + numpy
        try:
            import soundfile as sf
            import numpy as np

            data, sr = sf.read(str(in_path), dtype="float32")

            # Convert stereo to mono
            if data.ndim > 1:
                data = np.mean(data, axis=1)

            # Resample to 16kHz if necessary
            if sr != CANONICAL_SAMPLE_RATE:
                # Linear interpolation resampling
                duration = len(data) / float(sr)
                new_length = int(round(duration * CANONICAL_SAMPLE_RATE))
                x_old = np.linspace(0, duration, len(data), endpoint=False)
                x_new = np.linspace(0, duration, new_length, endpoint=False)
                data = np.interp(x_new, x_old, data)

            # Write 16-bit PCM WAV
            sf.write(str(out_path), data, CANONICAL_SAMPLE_RATE, subtype="PCM_16")
            logger.debug(f"Normalized audio via soundfile: {in_path} -> {out_path}")
            return out_path

        except Exception as sf_err:
            raise AudioNormalizationError(
                f"Failed to normalize audio '{in_path}' to WAV: {sf_err}"
            )
