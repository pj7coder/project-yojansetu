"""
JanSetu - Day 30: Eligibility Evaluation Command-Line Interface.

Commands:
  python -m app.evaluation.eligibility --gold-version v1 --split DEV
  python -m app.evaluation.eligibility --gold-version v1 --split VALIDATION
  python -m app.evaluation.eligibility --gold-version v1 --split TEST
  python -m app.evaluation.eligibility --case ELG-RJ-001 --verbose
  python -m app.evaluation.eligibility --tag EXCLUSION --tag BOUNDARY
  python -m app.evaluation.eligibility --persist
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import List, Optional

from app.evaluation.eligibility_runner import EligibilityBenchmarkRunner
from app.gold.schemas import GoldSplit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jansetu.evaluation.eligibility_cli")


def main(argv: Optional[List[str]] = None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="JanSetu Eligibility Evaluation Benchmark (Day 30)")
    parser.add_argument("--gold-version", default="v1", help="Target gold dataset version (default: v1)")
    parser.add_argument("--split", choices=["DEV", "VALIDATION", "TEST"], default="DEV", help="Dataset split to evaluate")
    parser.add_argument("--case", default=None, help="Evaluate a single case ID (e.g. ELG-RJ-001) with full drill-down")
    parser.add_argument("--tag", action="append", help="Filter benchmark cases by tag (e.g. --tag EXCLUSION)")
    parser.add_argument("--output-dir", default=None, help="Custom output directory to persist benchmark artifacts")
    parser.add_argument("--persist", action="store_true", default=True, help="Persist immutable run artifacts (default: True)")
    parser.add_argument("--no-persist", dest="persist", action="store_false", help="Skip artifact persistence")
    parser.add_argument("--verbose", action="store_true", help="Print detailed per-case trace information")

    args = parser.parse_args(argv)

    runner = EligibilityBenchmarkRunner(
        gold_version=args.gold_version,
        output_base_dir=Path(args.output_dir) if args.output_dir else None,
    )

    if args.case:
        print(f"\nEvaluating Single Eligibility Case: {args.case} ...")
        summary, results = runner.run_benchmark(
            split=GoldSplit(args.split),
            case_id_filter=args.case,
        )
        if not results:
            print(f"Error: Case '{args.case}' not found in split '{args.split}'.")
            sys.exit(1)

        c = results[0]
        print("=" * 72)
        print(f"Case ID:             {c.case_id} ({c.split.value})")
        print(f"Difficulty:          {c.difficulty.value}")
        print(f"Tags:                {', '.join(c.tags)}")
        print(f"Scheme ID:           {c.scheme_version_id}")
        print(f"Evaluation Date:     {c.evaluation_date or 'N/A'}")
        print("-" * 72)
        print(f"Gold Status:         {c.gold_status.value}")
        print(f"Actual Status:       {c.actual_status.value}")
        print(f"Status Match:        {'YES' if c.status_match else 'NO'}")
        print(f"Strict Pass:         {'YES' if c.strict_case_pass else 'NO'}")
        print(f"Duration:            {c.evaluation_duration_ms:.2f} ms")
        print("-" * 72)
        print(f"Gold Missing Fields: {c.gold_missing_fields}")
        print(f"Actual Missing:      {c.actual_missing_fields}")
        if c.missing_field_eval:
            print(f"Missing Precision:   {c.missing_field_eval.precision * 100:.1f}%")
            print(f"Missing Recall:      {c.missing_field_eval.recall * 100:.1f}%")
            print(f"Missing F1:          {c.missing_field_eval.f1 * 100:.1f}%")
            print(f"Unnecessary Qs:      {c.missing_field_eval.unnecessary_question_count}")
        print("-" * 72)
        print(f"Gold Decisive Rules: {c.gold_decisive_rules}")
        print(f"Actual Decisive:     {c.actual_decisive_rules}")
        if c.trace_eval:
            print(f"Trace Consistent:    {'YES' if c.trace_eval.status_trace_consistent else 'NO'}")
            print(f"Decisive Accuracy:   {c.trace_eval.decisive_rule_accuracy * 100:.1f}%")
            print(f"Evidence Valid:      {'YES' if c.trace_eval.evidence_references_valid else 'NO'}")

        if not c.strict_case_pass:
            print("-" * 72)
            print(f"FAILURE CLASSIFICATION:")
            print(f"  Code:        {c.failure_code.value if c.failure_code else 'UNKNOWN'}")
            print(f"  Severity:    {c.severity.value if c.severity else 'UNKNOWN'}")
            print(f"  Root Cause:  {c.root_cause.value if c.root_cause else 'UNKNOWN'}")
            print(f"  Reason:      {c.failure_reason}")

        if args.verbose and c.evaluation_trace:
            print("-" * 72)
            print("EVALUATION TRACE:")
            import json
            print(json.dumps(c.evaluation_trace, indent=2, default=str))

        print("=" * 72)
        return

    print(f"\n======================================================================")
    print(f"JANSETU - ELIGIBILITY EVALUATION BENCHMARK (Day 30)")
    print(f"Gold Dataset:  {args.gold_version} ({args.split})")
    if args.tag:
        print(f"Tag Filter:    {args.tag}")
    print(f"======================================================================\n")

    summary, results = runner.run_benchmark(
        split=GoldSplit(args.split),
        tag_filter=args.tag,
    )

    cm = summary.confusion_matrix
    print("\n" + "=" * 72)
    print(f"BENCHMARK SUMMARY ({summary.split.upper()})")
    print(f"Run ID:                      {summary.run_id}")
    print(f"Total Cases:                 {summary.case_count}")
    print(f"Status Accuracy:             {summary.status_accuracy * 100:.1f}%")
    print(f"Strict Case Pass Rate:       {summary.strict_case_pass_rate * 100:.1f}%")
    print("-" * 72)
    print(f"SAFETY COMPLIANCE & ACCURACY METRICS:")
    print(f"  Critical False Eligibility:  {cm.critical_false_eligibility_count} (Ineligible -> Eligible)")
    print(f"  Critical False Rejection:    {cm.critical_false_ineligibility_count} (Eligible -> Ineligible)")
    print(f"  Premature Decisions:         {cm.high_premature_eligibility_count + cm.high_premature_ineligibility_count} (MoreInfo -> Decided)")
    print(f"  Unnecessary Questions:       {summary.total_unnecessary_questions}")
    print(f"  Missing Field Precision:     {summary.missing_field_precision * 100:.1f}%")
    print(f"  Missing Field Recall:        {summary.missing_field_recall * 100:.1f}%")
    print(f"  Missing Field F1:            {summary.missing_field_f1 * 100:.1f}%")
    print(f"  Trace Decisive Accuracy:     {summary.trace_decisive_accuracy * 100:.1f}%")
    print(f"  Evidence Valid Rate:         {summary.trace_evidence_accuracy * 100:.1f}%")
    print("-" * 72)
    print(f"EXECUTION LATENCY:")
    print(f"  Mean Latency:                {summary.duration_mean_ms:.2f} ms")
    print(f"  P50 Median:                  {summary.duration_p50_ms:.2f} ms")
    print(f"  P95 Latency:                 {summary.duration_p95_ms:.2f} ms")
    print("-" * 72)
    print("CONFUSION MATRIX (Gold \\ Predicted):")
    print(f"  ELIGIBLE:      {cm.eligible_eligible:3d} ELG | {cm.eligible_not_eligible:3d} NOT_ELG | {cm.eligible_more_info:3d} MORE_INFO")
    print(f"  NOT_ELIGIBLE:  {cm.not_eligible_eligible:3d} ELG | {cm.not_eligible_not_eligible:3d} NOT_ELG | {cm.not_eligible_more_info:3d} MORE_INFO")
    print(f"  MORE_INFO:     {cm.more_info_eligible:3d} ELG | {cm.more_info_not_eligible:3d} NOT_ELG | {cm.more_info_more_info:3d} MORE_INFO")
    print("=" * 72)

    if args.persist:
        run_dir = runner.persist_run(summary, results)
        print(f"\n[SAVED] Immutable Run Artifacts Persisted To:\n   {run_dir}\n")


if __name__ == "__main__":
    main()
