"""
JanSetu - Day 28: Gold Dataset CLI Utilities.

Entrypoints:
  python -m app.gold.validate [--version v1]
  python -m app.gold.summary [--version v1]
  python -m app.gold.freeze [--version v1.0]
"""

import argparse
import json
import sys
from pathlib import Path

from app.gold.hashing import compute_manifest_hash
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import GoldDatasetManifest
from app.gold.summary import GoldDatasetReporter
from app.gold.validator import GoldDatasetValidator


def run_validate(args):
    """Validates the gold dataset for schema, integrity, evidence, and privacy."""
    loader = GoldBenchmarkLoader(version=args.version)
    validator = GoldDatasetValidator()

    print(f"Loading gold dataset manifest from: {loader.manifest_path}")
    try:
        manifest = loader.load_manifest()
    except Exception as e:
        print(f"FAILED to load manifest: {e}")
        sys.exit(1)

    all_cases = loader.load_cases(status=None)
    print(f"Loaded {len(all_cases)} gold cases across {len(manifest.task_counts)} tasks.")

    all_errors = []

    # 1. Validate manifest consistency
    manifest_errors = validator.validate_manifest(manifest, all_cases)
    if manifest_errors:
        all_errors.extend(manifest_errors)

    # 2. Validate individual cases
    for case in all_cases:
        t = case.task.value
        if t == "extraction":
            errs = validator.validate_extraction_case(case)
        elif t == "eligibility":
            errs = validator.validate_eligibility_case(case)
        elif t == "search":
            errs = validator.validate_search_case(case)
        elif t == "voice":
            errs = validator.validate_voice_case(case)
        elif t == "conversation":
            errs = validator.validate_conversation_case(case)
        else:
            errs = [f"Unknown task {t}"]
        all_errors.extend(errs)

    if all_errors:
        print(f"\n[VALIDATION FAILED] Found {len(all_errors)} error(s):")
        for idx, err in enumerate(all_errors, start=1):
            print(f"  {idx}. {err}")
        sys.exit(1)
    else:
        print(f"\n[VALIDATION PASSED] All {len(all_cases)} gold cases verified successfully.")
        print("  - Zero duplicate IDs")
        print("  - Zero PII leaks")
        print("  - All evidence references and audio hashes valid")
        print("  - All tri-state eligibility statuses conform to Day 14 specification")
        sys.exit(0)


def run_summary(args):
    """Outputs structured dataset summary and coverage distribution."""
    loader = GoldBenchmarkLoader(version=args.version)
    reporter = GoldDatasetReporter(loader)
    print(reporter.format_console_summary())


def run_freeze(args):
    """
    Computes canonical manifest hash and updates dataset_sha256 in manifest.json.
    """
    loader = GoldBenchmarkLoader(version=args.version)
    manifest_path = loader.manifest_path
    if not manifest_path.is_file():
        print(f"Manifest not found at {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Re-aggregate task and split counts directly from case catalog
    task_counts = {}
    split_counts = {}
    for item in data.get("cases", []):
        t = item.get("task")
        s = item.get("split")
        task_counts[t] = task_counts.get(t, 0) + 1
        if t not in split_counts:
            split_counts[t] = {}
        split_counts[t][s] = split_counts[t].get(s, 0) + 1

    data["task_counts"] = task_counts
    data["split_counts"] = split_counts

    manifest_hash = compute_manifest_hash(data)
    data["dataset_sha256"] = manifest_hash

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Successfully frozen dataset v{data.get('dataset_version', '1.0')}:")
    print(f"  Manifest: {manifest_path}")
    print(f"  Total Cases: {len(data.get('cases', []))}")
    print(f"  SHA-256: {manifest_hash}")


def main():
    parser = argparse.ArgumentParser(description="JanSetu Gold Dataset Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate command
    val_p = subparsers.add_parser("validate", help="Validate gold dataset integrity")
    val_p.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    val_p.set_defaults(func=run_validate)

    # Summary command
    sum_p = subparsers.add_parser("summary", help="Summarize gold dataset coverage")
    sum_p.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    sum_p.set_defaults(func=run_summary)

    # Freeze command
    frz_p = subparsers.add_parser("freeze", help="Freeze dataset and compute canonical SHA-256")
    frz_p.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    frz_p.set_defaults(func=run_freeze)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
