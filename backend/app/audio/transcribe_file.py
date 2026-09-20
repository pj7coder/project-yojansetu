"""
JanSetu - Day 23: Audio Transcription CLI Tool.

Usage:
    python -m app.audio.transcribe_file path/to/audio.wav

Performs offline audio validation, 16kHz mono normalization, Silero VAD segmentation,
and Whisper transcription. Prints concise diagnostic report for developers.
"""

import argparse
import sys
from pathlib import Path

from app.audio.transcription import AudioTranscriptionService


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio file using JanSetu offline audio front-end + STT."
    )
    parser.add_argument("audio_path", type=str, help="Path to input audio file")
    parser.add_argument("--language", type=str, default="hi", help="Language code (default: hi)")
    args = parser.parse_args()

    audio_path = Path(args.audio_path).resolve()
    if not audio_path.exists():
        print(f"[ERROR] Audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    print(f"=== JanSetu Audio Front-End CLI ===")
    print(f"Input: {audio_path.name}")
    print(f"Processing...")

    service = AudioTranscriptionService()
    result = service.transcribe_audio(audio_path, filename_hint=audio_path.name, language=args.language)

    print(f"\n--- Result ---")
    print(f"Status:            {result.status.value}")
    print(f"Speech Detected:   {result.speech_detected}")
    print(f"Original Duration: {result.original_duration_ms} ms")
    print(f"Speech Duration:   {result.speech_duration_ms} ms")

    if result.quality:
        print(f"RMS Level:         {result.quality.rms_level:.6f}")
        print(f"Peak Amplitude:    {result.quality.peak_amplitude:.6f}")
        print(f"Too Quiet:         {result.quality.is_too_quiet}")
        print(f"Clipping:          {result.quality.is_clipping}")

    print(f"\n--- Utterance Segments ({len(result.segments)}) ---")
    for seg in result.segments:
        print(f"[{seg.segment_id}] {seg.start_ms}ms -> {seg.end_ms}ms: {seg.text}")

    print(f"\n--- Combined Transcript ---")
    print(result.text if result.text else "(none)")

    print(f"\n--- Latency Breakdown ---")
    for k, v in result.timings.items():
        print(f"{k:15s}: {v:.1f} ms")


if __name__ == "__main__":
    main()
