"""
JanSetu - Day 29: Benchmark Command-Line Interface.

Commands:
  python -m app.evaluation.extraction --gold-version v1 --split DEV
  python -m app.evaluation.extraction --gold-version v1 --split VALIDATION
  python -m app.evaluation.extraction --gold-version v1 --split TEST
  python -m app.evaluation.extraction --case EXT-RJ-001 --verbose
  python -m app.evaluation.extraction --tag OCR --tag TABLE
"""

import argparse
import logging
import sys
from typing import List, Optional

from app.evaluation.extraction_runner import ExtractionBenchmarkRunner
from app.gold.schemas import GoldSplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jansetu.evaluation.cli")


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="JanSetu Extraction Evaluation Benchmark (Day 29)")
    parser.add_argument("--gold-version", default="v1", help="Target gold dataset version (default: v1)")
    parser.add_argument("--split", choices=["DEV", "VALIDATION", "TEST"], default="DEV", help="Dataset split to evaluate")
    parser.add_argument("--case", default=None, help="Evaluate a single case ID (e.g. EXT-RJ-001) with full drill-down")
    parser.add_argument("--tag", action="append", help="Filter benchmark cases by tag (e.g. --tag OCR --tag TABLE)")
    parser.add_argument("--provider", default=None, choices=["ollama", "mock"], help="LLM provider override (default: settings.llm_provider)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed per-fact diagnostic comparison")

    args = parser.parse_args(argv)

    extraction_service = None
    if args.provider:
        from app.extraction.service import SchemeExtractionService
        from app.llm.mock import MockLLMProvider
        from app.llm.ollama import OllamaProvider
        provider_inst = MockLLMProvider() if args.provider == "mock" else OllamaProvider()
        extraction_service = SchemeExtractionService(llm_provider=provider_inst)

    runner = ExtractionBenchmarkRunner(gold_version=args.gold_version, extraction_service=extraction_service)

    if args.case:
        print(f"\nEvaluating Single Case: {args.case} ...")
        summary, manifest, results = runner.run_benchmark(
            split=GoldSplit(args.split),
            case_id_filter=args.case,
        )
        if not results:
            print(f"Error: Case '{args.case}' not found in split '{args.split}'.")
            sys.exit(1)

        c = results[0]
        print("=" * 70)
        print(f"Case ID:        {c.case_id} ({c.split.value})")
        print(f"Difficulty:     {c.difficulty.value}")
        print(f"Tags:           {', '.join(c.tags)}")
        print(f"Format:         {c.source_format} | Layout: {c.layout_type} | Lang: {c.language}")
        print(f"Strict Pass:    {c.strict_case_pass}")
        print(f"Critical Pass:  {c.critical_fact_pass}")
        print(f"Precision:      {c.field_precision * 100:.1f}%")
        print(f"Recall:         {c.field_recall * 100:.1f}%")
        print(f"F1:             {c.field_f1 * 100:.1f}%")
        print(f"Norm Value Acc: {c.value_normalized_accuracy * 100:.1f}%")
        print(f"Operator Acc:   {c.operator_accuracy * 100:.1f}%")
        print(f"Rule Tree Match:{c.rule_tree_exact_match}")
        print("-" * 70)
        print("Facts Evaluated:")
        for fe in c.fact_evaluations:
            status_icon = "PASS" if fe.value_normalized_match else "FAIL"
            print(f"  [{status_icon}] Field: {fe.field}")
            print(f"         Gold: {fe.gold_value} ({fe.gold_operator})")
            print(f"         Pred: {fe.predicted_value} ({fe.predicted_operator})")
            if fe.failure_code:
                print(f"         Failure: {fe.failure_code.value} ({fe.severity.value if fe.severity else ''})")
                print(f"         Attribution: {fe.attribution_stage.value if fe.attribution_stage else 'N/A'}")
                print(f"         Reason: {fe.reason}")
        print("=" * 70)
        return

    print(f"\n======================================================================")
    print(f"JANSETU - EXTRACTION BENCHMARK RUNNER (Day 29)")
    print(f"Gold Dataset:  {args.gold_version} ({args.split})")
    if args.tag:
        print(f"Tag Filter:    {args.tag}")
    print(f"======================================================================\n")

    summary, manifest, results = runner.run_benchmark(
        split=GoldSplit(args.split),
        tag_filter=args.tag,
    )

    print("\n" + "=" * 70)
    print(f"EXTRACTION BENCHMARK SUMMARY ({manifest.split.value})")
    print(f"Run ID:                    {manifest.run_id}")
    print(f"Total Cases:               {summary.total_cases}")
    print(f"Strict Case Pass Rate:     {summary.strict_case_pass_rate * 100:.1f}% ({summary.strict_case_pass_count}/{summary.total_cases})")
    print(f"Critical Fact Pass Rate:   {summary.critical_fact_pass_rate * 100:.1f}% ({summary.critical_fact_pass_count}/{summary.total_cases})")
    print("-" * 70)
    print(f"Field Precision:           {summary.field_precision * 100:.1f}%")
    print(f"Field Recall:              {summary.field_recall * 100:.1f}%")
    print(f"Field F1 Score:            {summary.field_f1 * 100:.1f}%")
    print(f"Exact Value Accuracy:      {summary.value_exact_accuracy * 100:.1f}%")
    print(f"Normalized Value Accuracy: {summary.value_normalized_accuracy * 100:.1f}%")
    print(f"Operator Accuracy:         {summary.operator_accuracy * 100:.1f}%")
    print(f"Rule Tree Exact Match:     {summary.rule_tree_exact_match_rate * 100:.1f}%")
    print(f"Evidence Grounding Rate:   {summary.evidence_grounding_rate * 100:.1f}%")
    print(f"Hallucination Rate:        {summary.hallucination_rate * 100:.1f}%")
    print(f"Critical Hallucinations:   {summary.critical_hallucination_count}")
    print("-" * 70)
    print("Critical Safety Errors:")
    for k, v in summary.critical_safety_errors.items():
        print(f"  - {k}: {v}")
    print("-" * 70)
    print("Pipeline Attribution Stages:")
    for k, v in summary.pipeline_attribution_counts.items():
        print(f"  - {k}: {v}")
    print("=" * 70)
    print(f"Artifacts stored in: storage/benchmarks/extraction/{manifest.run_id}/\n")


if __name__ == "__main__":
    main()
