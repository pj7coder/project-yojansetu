"""
YojanSetu - Day 32: Voice Benchmark CLI Entrypoint.

Usage:
    python -m app.evaluation.voice --gold-version v1 --split DEV
    python -m app.evaluation.voice --gold-version v1 --split VALIDATION
    python -m app.evaluation.voice --gold-version v1 --split TEST
    python -m app.evaluation.voice --case VOICE-RJ-001 --verbose
    python -m app.evaluation.voice --tag SHORT_ANSWER --tag NOISY
"""

import argparse
import logging
from pathlib import Path
import sys

from app.evaluation.voice_runner import VoiceBenchmarkRunner
from app.gold.schemas import GoldSplit

logger = logging.getLogger("yojansetu.evaluation.voice")


def parse_args():
    parser = argparse.ArgumentParser(
        description="YojanSetu Day 32 - Voice System Quality Benchmark Runner"
    )
    parser.add_argument(
        "--gold-version",
        type=str,
        default="v1",
        help="Gold dataset version to evaluate against (default: v1)",
    )
    parser.add_argument(
        "--split",
        type=str,
        choices=["DEV", "VALIDATION", "TEST"],
        default="DEV",
        help="Dataset split to evaluate (default: DEV)",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Filter evaluation to a single case ID (e.g. VOICE-RJ-001)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        action="append",
        dest="tags",
        help="Filter cases by tag (can specify multiple e.g. --tag SHORT_ANSWER)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Disable persisting benchmark artifacts to storage/benchmarks/voice/",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed debug logging and per-case output",
    )
    return parser.parse_args()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    split_enum = GoldSplit(args.split)
    tag_filter = args.tags[0] if args.tags else None

    runner = VoiceBenchmarkRunner()
    summary, cases = runner.run_benchmark(
        split=split_enum,
        gold_version=args.gold_version,
        case_id_filter=args.case,
        tag_filter=tag_filter,
        persist_results=not args.no_persist,
    )

    print("=" * 80)
    print("  YOJANSETU — VOICE SYSTEM QUALITY BENCHMARK (DAY 32)")
    print(f"  Gold Version: {summary.gold_version} | Split: {summary.split}")
    if args.case:
        print(f"  Target Case: {args.case}")
    print("=" * 80)
    print()
    print("-" * 80)
    print(f"  BENCHMARK SUMMARY — Run ID: {summary.run_id}")
    print("-" * 80)
    print(f"  Voice Cases Evaluated:       {summary.total_voice_cases}")
    print(f"  Conversation Cases:          {summary.total_conversation_cases}")
    print(f"  Strict Turn Pass Rate:       {summary.strict_turn_pass_rate * 100:.1f}%")
    print(f"  End-to-End Critical Values:  {summary.end_to_end_critical_value_pass_rate * 100:.1f}%")
    print(f"  Conversation State Accuracy: {summary.conversation_state_pass_rate * 100:.1f}%")
    print(f"  Critical Failures Count:     {summary.critical_failures_count}")
    print()
    print("  [Stage 1: Silero VAD]")
    print(f"  - Speech Recall:             {summary.vad_metrics.speech_detection_recall * 100:.1f}%")
    print(f"  - Speech Precision:          {summary.vad_metrics.speech_detection_precision * 100:.1f}%")
    print(f"  - Short-Answer Retention:    {summary.vad_metrics.short_answer_retention * 100:.1f}%")
    print(f"  - False Positives / Missed:  {summary.vad_metrics.false_positive_count} / {summary.vad_metrics.missed_utterance_count}")
    print()
    print("  [Stage 2: STT Semantic Entities]")
    print(f"  - Word Error Rate (WER):     {summary.stt_metrics.wer * 100:.1f}%")
    print(f"  - Age Accuracy (62 vs 26):   {summary.stt_metrics.age_accuracy * 100:.1f}%")
    print(f"  - Income Accuracy (1.5L):    {summary.stt_metrics.income_accuracy * 100:.1f}%")
    print(f"  - District Accuracy:         {summary.stt_metrics.district_accuracy * 100:.1f}%")
    print(f"  - Negation Accuracy ('नहीं'): {summary.stt_metrics.negation_accuracy * 100:.1f}%")
    print()
    print("  [Stage 3 & 4: Profile & Confirmation Safety]")
    print(f"  - Value Extraction Accuracy: {summary.profile_metrics.normalized_value_accuracy * 100:.1f}%")
    print(f"  - Unsupported Inferences:    {summary.profile_metrics.unsupported_inferred_critical_facts} (TARGET: 0)")
    print(f"  - Confirmation Trigger Rate: {summary.confirmation_metrics.critical_confirmation_trigger_rate * 100:.1f}%")
    print(f"  - Contextual YES / NO:       {summary.confirmation_metrics.contextual_yes_accuracy * 100:.1f}% / {summary.confirmation_metrics.contextual_no_accuracy * 100:.1f}%")
    print()
    print("  [Stage 6: TTS Normalization QA]")
    print(f"  - Numeric Pronunciation:     {summary.tts_metrics.number_pronunciation_accuracy * 100:.1f}%")
    print(f"  - Currency Pronunciation:    {summary.tts_metrics.currency_pronunciation_accuracy * 100:.1f}%")
    print(f"  - Boundary Word Preservation:{summary.tts_metrics.boundary_preservation_accuracy * 100:.1f}%")
    print()
    print("  [Latency Profiling]")
    print(f"  - Latency (P50 / P95 / Avg): {summary.latency_metrics.p50_total_ms:.2f}ms / {summary.latency_metrics.p95_total_ms:.2f}ms / {summary.latency_metrics.avg_total_ms:.2f}ms")
    print(f"  - Offline Execution Mode:    {'100% AIR-GAPPED' if summary.offline_functional else 'DEGRADED'}")
    print("-" * 80)
    print()

    if args.verbose and cases:
        print("=" * 80)
        print("  DETAILED CASE-BY-CASE DIAGNOSTICS")
        print("=" * 80)
        for c in cases:
            status_tag = "[PASS]" if c.strict_pass else "[FAIL]"
            print()
            print(f"{status_tag} Case {c.case_id} ({c.noise_condition}) | Duration: {c.duration_ms:.2f}ms")
            print(f"  Reference Transcript:     {c.reference_transcript}")
            print(f"  Hypothesis Transcript:    {c.hypothesis_transcript}")
            print(f"  Expected Field / Value:   {c.expected_field} = {c.expected_value}")
            print(f"  Extracted Field / Value:  {c.extracted_field} = {c.extracted_value}")
            print(f"  VAD Match: {c.vad_match} | STT Semantic: {c.stt_semantic_pass} | Profile Match: {c.profile_match}")
            if c.failure_codes:
                print(f"  Failure Codes:            {c.failure_codes}")
        print("=" * 80)

    if not args.no_persist:
        run_output_dir = runner.output_base_dir / summary.run_id
        print(f"  Report saved to: {run_output_dir / 'report.md'}")
        print(f"  Artifacts saved in: {run_output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
