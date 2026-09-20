"""
JanSetu - Day 28: Gold Dataset Summary & Reporting Utilities.

Generates aggregate metrics, task and split distributions, coverage matrices,
and human review reports.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import GoldDatasetManifest


class GoldDatasetReporter:
    """
    Generates statistics and coverage reports for the gold dataset.
    """

    def __init__(self, loader: Optional[GoldBenchmarkLoader] = None):
        self.loader = loader or GoldBenchmarkLoader()

    def generate_summary(self) -> Dict[str, Any]:
        """Calculates comprehensive dataset statistics."""
        manifest: GoldDatasetManifest = self.loader.load_manifest()
        cases = self.loader.load_cases(status=None)  # Load all statuses

        task_counts = Counter()
        split_counts = defaultdict(Counter)
        status_counts = Counter()
        difficulty_counts = Counter()
        tag_counts = Counter()
        ambiguities = []

        for c in cases:
            task_counts[c.task.value] += 1
            split_counts[c.task.value][c.split.value] += 1
            status_counts[c.status.value] += 1
            difficulty_counts[c.difficulty.value] += 1
            for tag in c.tags:
                tag_counts[tag] += 1
            if c.ambiguity_flag:
                ambiguities.append({
                    "case_id": c.case_id,
                    "task": c.task.value,
                    "type": c.ambiguity_flag.value,
                    "notes": c.notes,
                })

        return {
            "dataset_version": manifest.dataset_version,
            "dataset_sha256": manifest.dataset_sha256,
            "total_cases": len(cases),
            "task_counts": dict(task_counts),
            "split_counts": {k: dict(v) for k, v in split_counts.items()},
            "status_counts": dict(status_counts),
            "difficulty_counts": dict(difficulty_counts),
            "top_tags": dict(tag_counts.most_common(20)),
            "ambiguities": ambiguities,
        }

    def format_console_summary(self) -> str:
        """Formats the summary as a readable terminal string."""
        summary = self.generate_summary()
        lines = [
            "=" * 70,
            f"JANSETU — GOLD EVALUATION DATASET SUMMARY (v{summary['dataset_version']})",
            f"Dataset SHA-256: {summary['dataset_sha256'] or 'NOT_FROZEN'}",
            f"Total Registered Cases: {summary['total_cases']}",
            "=" * 70,
            "",
            "--- Task & Split Distribution ---",
            f"{'Task':<15} | {'DEV':<8} | {'VALIDATION':<12} | {'TEST':<8} | {'TOTAL':<8}",
            "-" * 60,
        ]

        for task, splits in summary["split_counts"].items():
            dev = splits.get("DEV", 0)
            val = splits.get("VALIDATION", 0)
            test = splits.get("TEST", 0)
            tot = dev + val + test
            lines.append(f"{task:<15} | {dev:<8} | {val:<12} | {test:<8} | {tot:<8}")

        lines.extend([
            "-" * 60,
            "",
            "--- Review Status ---",
        ])
        for status, count in summary["status_counts"].items():
            lines.append(f"  • {status}: {count}")

        lines.extend([
            "",
            "--- Difficulty ---",
        ])
        for diff, count in summary["difficulty_counts"].items():
            lines.append(f"  • {diff}: {count}")

        lines.extend([
            "",
            "--- Top Coverage Tags ---",
        ])
        for tag, count in summary["top_tags"].items():
            lines.append(f"  • {tag}: {count}")

        if summary["ambiguities"]:
            lines.extend([
                "",
                f"--- Ambiguities & Conflicts ({len(summary['ambiguities'])}) ---",
            ])
            for a in summary["ambiguities"]:
                lines.append(f"  • [{a['type']}] {a['case_id']} ({a['task']}): {a['notes']}")

        lines.append("=" * 70)
        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from app.gold.cli import run_summary
    parser = argparse.ArgumentParser(description="Summarize JanSetu Gold Dataset")
    parser.add_argument("--version", default="v1", help="Dataset version folder (default: v1)")
    args = parser.parse_args()
    run_summary(args)
