"""
YojanSetu - Day 31: Search & Scheme Discovery Evaluation CLI.

Command line interface for running search quality benchmarks:
Usage:
  python -m app.evaluation.search --gold-version v1 --split DEV
  python -m app.evaluation.search --split TEST --verbose
  python -m app.evaluation.search --case SRCH-RJ-001 --verbose
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.evaluation.search_runner import SearchBenchmarkRunner
from app.gold.schemas import GoldSplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YojanSetu - Day 31: Search & Scheme Discovery Evaluation Benchmark"
    )
    parser.add_argument(
        "--gold-version",
        type=str,
        default="v1",
        help="Gold benchmark dataset version (default: v1)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="DEV",
        choices=["DEV", "VALIDATION", "TEST"],
        help="Dataset partition to benchmark (default: DEV)",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Filter to run a single case (e.g. SRCH-RJ-001)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        action="append",
        dest="tags",
        help="Filter by case tag(s) (e.g. --tag HINDI --tag HINGLISH)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Top-K recommendations cutoff (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed case diagnostics output",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not save benchmark run artifacts to disk",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    print("=" * 80)
    print("  YOJANSETU — SCHEME DISCOVERY & SEARCH QUALITY BENCHMARK (DAY 31)")
    print(f"  Gold Version: {args.gold_version} | Split: {args.split} | Top-K: {args.k}")
    if args.case:
        print(f"  Target Case: {args.case}")
    if args.tags:
        print(f"  Target Tags: {args.tags}")
    print("=" * 80)

    runner = SearchBenchmarkRunner(gold_version=args.gold_version)

    summary, case_results = runner.run_benchmark(
        split=args.split,
        tag_filter=args.tags,
        case_id_filter=args.case,
        top_k=args.k,
        persist_results=not args.no_persist,
    )

    # Print summary results table
    cm = summary.candidate_metrics
    rm = summary.ranking_metrics
    bm = summary.bucket_metrics
    mm = summary.multilingual_metrics
    ih = summary.index_health

    print("\n" + "-" * 80)
    print(f"  BENCHMARK SUMMARY — Run ID: {summary.run_id}")
    print("-" * 80)
    print(f"  Cases Evaluated:             {summary.total_cases}")
    print(f"  Strict Search Case Pass:     {summary.strict_pass_count} / {summary.total_cases} ({summary.strict_case_pass_rate * 100:.1f}%)")
    print(f"  Ranking-Only Pass Rate:      {summary.ranking_only_pass_rate * 100:.1f}%")
    print("")
    print("  [Stage B: Candidate Filtering]")
    print(f"  - Candidate Recall:          {cm.candidate_recall * 100:.1f}% ({cm.candidate_surviving_relevant_schemes}/{cm.total_gold_relevant_schemes})")
    print(f"  - Candidate Precision:       {cm.candidate_precision * 100:.1f}%")
    print(f"  - Unknown-Field Recall:      {cm.unknown_field_candidate_recall * 100:.1f}%")
    print(f"  - Unknown Profile False Neg: {cm.unknown_profile_filter_false_negatives} (target: 0)")
    print("")
    print("  [Stage C: Eligibility Bucketing & Output Safety]")
    print(f"  - Ineligible Leakage Count:  {bm.ineligible_leakage_count} (SAFETY TARGET: 0)")
    print(f"  - Eligible Bucket Accuracy:  {bm.eligible_bucket_accuracy * 100:.1f}%")
    print(f"  - More-Info Bucket Accuracy: {bm.more_info_bucket_accuracy * 100:.1f}%")
    print(f"  - Duplicate Result Count:    {bm.duplicate_scheme_results}")
    print("")
    print("  [Stage D: Semantic Ranking Quality]")
    print(f"  - Recall@1 / @3 / @5:        {rm.recall_at_1 * 100:.1f}% / {rm.recall_at_3 * 100:.1f}% / {rm.recall_at_5 * 100:.1f}%")
    print(f"  - Precision@5:               {rm.precision_at_5 * 100:.1f}%")
    print(f"  - Mean Reciprocal Rank (MRR):{rm.mrr:.4f}")
    print(f"  - NDCG@5:                    {rm.ndcg_at_5:.4f}")
    print(f"  - Top-Set Recall:            {rm.top_set_recall * 100:.1f}%")
    print(f"  - Exact Name Hit Rate:       {rm.exact_name_hit_rate * 100:.1f}%")
    print(f"  - No-Result False Rec Rate:  {rm.false_recommendation_rate_on_no_result_cases * 100:.1f}% (target: 0.0%)")
    print("")
    print("  [Multilingual Breakdown]")
    print(f"  - Hindi Recall@5:            {mm.hindi.recall_at_5 * 100:.1f}% (MRR: {mm.hindi.mrr:.4f})")
    print(f"  - English Recall@5:          {mm.english.recall_at_5 * 100:.1f}% (MRR: {mm.english.mrr:.4f})")
    print(f"  - Hinglish Recall@5:         {mm.hinglish.recall_at_5 * 100:.1f}% (MRR: {mm.hinglish.mrr:.4f})")
    if mm.dialect.total_cases > 0:
        print(f"  - Dialect Status:            {mm.dialect.status_note or 'Evaluated'}")
    print("")
    print("  [Latency Profiling]")
    print(f"  - Latency (P50 / P95 / Avg): {summary.p50_duration_ms:.2f}ms / {summary.p95_duration_ms:.2f}ms / {summary.avg_duration_ms:.2f}ms")
    print(f"  - Index Coverage:            {ih.index_coverage_pct:.1f}% ({ih.indexed_current_scheme_count}/{ih.verified_scheme_count})")
    print("-" * 80)

    # Detailed verbose output for single case or all cases
    if args.verbose:
        print("\n" + "=" * 80)
        print("  DETAILED CASE-BY-CASE DIAGNOSTICS")
        print("=" * 80)
        for c in case_results:
            status_symbol = "PASS" if c.strict_case_pass else "FAIL"
            print(f"\n[{status_symbol}] Case {c.case_id} ({c.language}) | Duration: {c.duration_ms}ms")
            print(f"  Query:               {c.query}")
            print(f"  Profile (Safe):      {c.profile_summary}")
            print(f"  Expected Relevant:   {c.gold_relevant_scheme_ids} (Empty: {c.expected_empty})")
            print(f"  SQL Candidates:      {c.sql_candidate_count} candidates")
            print(f"  Ranked Eligible:     {c.ranked_eligible_ids}")
            print(f"  Ranked More-Info:    {c.ranked_more_info_ids}")
            print(f"  Target Similarity:   {c.target_semantic_similarity} | Target Rank: {c.target_rank}")
            print(f"  Recall@5: {c.recalls.get(5, 0.0)} | MRR: {c.reciprocal_rank} | NDCG@5: {c.ndcg_at_5}")
            if c.diagnoses:
                print("  Diagnosed Failures:")
                for d in c.diagnoses:
                    print(f"    - [{d.stage.value}] {d.code.value} ({d.severity}): {d.description}")

    if not args.no_persist:
        run_path = runner.output_base_dir / summary.run_id
        print(f"\n  Report saved to: {run_path / 'report.md'}")
        print(f"  Artifacts saved in: {run_path}")

    print("=" * 80)


if __name__ == "__main__":
    main()
