"""
YojanSetu - Day 26: Standalone Synthesis CLI.

Utility for developers and evaluators to quickly synthesize arbitrary text
using local offline TTS providers and export audio to a specified WAV file.

Usage:
    python -m app.tts.synthesize --text "आपकी आयु क्या है?" --output test.wav
    python -m app.tts.synthesize --text "आपने ₹1,50,000 आय बताई है।" --provider mms
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.tts.service import get_speech_synthesis_service


async def async_main():
    parser = argparse.ArgumentParser(description="YojanSetu Offline Speech Synthesizer CLI")
    parser.add_argument("--text", type=str, required=True, help="Text to speak")
    parser.add_argument("--output", type=str, default="output.wav", help="Output WAV file path")
    parser.add_argument("--language", type=str, default="hi", help="Language code ('hi' or 'en')")
    parser.add_argument("--provider", type=str, default=None, help="TTS provider ('mms', 'piper', 'mock')")
    parser.add_argument("--voice", type=str, default=None, help="Voice name")
    parser.add_argument("--rate", type=float, default=1.0, help="Speaking rate multiplier")

    args = parser.parse_args()

    # Configure utf-8 standard output
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    service = get_speech_synthesis_service()
    print(f"Synthesizing: '{args.text}'")
    print(f"Provider: {args.provider or service.settings.tts_default_provider}")

    result = await service.synthesize_text(
        text=args.text,
        language=args.language,
        voice=args.voice,
        speaking_rate=args.rate,
        provider_name=args.provider,
    )

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy temporary result to requested output
    with open(result.audio_path, "rb") as src, open(out_path, "wb") as dst:
        dst.write(src.read())

    print(f"Success! Audio saved to: {out_path}")
    print(f"Duration: {result.duration_ms:.1f}ms | Synthesis Latency: {result.synthesis_ms:.1f}ms | RTF: {result.rtf}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
