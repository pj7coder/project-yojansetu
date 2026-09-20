"""
JanSetu - Day 22: Speech-to-Text Benchmark Runner and CLI.

Orchestrates local offline benchmarking across candidate STT models:
- Loads benchmark dataset manifest
- Normalizes test audio files to standard 16kHz mono baseline
- Runs batch_size=1 inference measuring cold/warm latency and RTF
- Evaluates literal transcription metrics (WER, CER)
- Evaluates task-semantic critical entity metrics (Age, Income, District, Negation, Terms)
- Isolates errors per sample and per provider (no crash on single failure)
- Generates persistent result artifacts: summary.json, samples.jsonl, critical_failures.json, report.md
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from app.stt.audio_normalizer import AudioNormalizationError, AudioNormalizer
from app.stt.config import STTSettings, get_stt_settings
from app.stt.interface import SpeechToTextProvider
from app.stt.metrics import BenchmarkMetricsEvaluator
from app.stt.providers.indic_asr import IndicASRSTTProvider
from app.stt.providers.mock import MockSTTProvider
from app.stt.providers.whisper import WhisperSTTProvider
from app.stt.schemas import (
    BenchmarkCategory,
    BenchmarkSample,
    BenchmarkSummary,
    CriticalEntityTarget,
    CriticalFailureItem,
    SampleResult,
    STTResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("jansetu.stt.benchmark")


class STTBenchmarkRunner:
    """Executes STT benchmark against a standardized dataset."""

    def __init__(self, settings: Optional[STTSettings] = None):
        self.settings = settings or get_stt_settings()

    def load_manifest(self, dataset_path: Path) -> List[BenchmarkSample]:
        """Loads and parses benchmark dataset manifest.json."""
        manifest_file = dataset_path / "manifest.json"
        if not manifest_file.is_file():
            raise FileNotFoundError(f"Benchmark manifest not found at: {manifest_file}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        samples: List[BenchmarkSample] = []
        for item in raw_data.get("samples", []):
            samples.append(BenchmarkSample(**item))

        logger.info(f"Loaded {len(samples)} benchmark samples from {manifest_file}")
        return samples

    def _measure_resources(self) -> Tuple[Optional[float], Optional[float]]:
        """Returns (RAM_MB, VRAM_MB)."""
        ram_mb = None
        vram_mb = None
        try:
            import psutil
            process = psutil.Process(os.getpid())
            ram_mb = round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            pass

        try:
            import torch
            if torch.cuda.is_available():
                vram_mb = round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
        except Exception:
            pass
        return ram_mb, vram_mb

    def run_provider_benchmark(
        self,
        provider: SpeechToTextProvider,
        samples: List[BenchmarkSample],
        dataset_path: Path,
        output_dir: Path,
        run_id_prefix: str = "run",
    ) -> Tuple[BenchmarkSummary, List[CriticalFailureItem]]:
        """
        Executes benchmark run for a single STT provider.
        Isolates per-sample failures so that corrupted audio or inference errors
        do not terminate the evaluation.
        """
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"{run_id_prefix}_{provider.provider_id}_{timestamp_str}"
        run_out_dir = output_dir / run_id
        run_out_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"--- Starting Benchmark Run: {run_id} ({provider.provider_id} / {provider.model_name}) ---")

        # 1. Load Model and measure load latency + resource footprint
        ram_before, _ = self._measure_resources()
        t0_load = time.perf_counter()
        try:
            provider.load()
            load_time_sec = time.perf_counter() - t0_load
        except Exception as load_err:
            logger.warning(
                f"PROVIDER_UNAVAILABLE: Provider '{provider.provider_id}' failed to load: {load_err}"
            )
            unavail_summary = BenchmarkSummary(
                benchmark_run_id=run_id,
                timestamp=datetime.now(timezone.utc),
                provider=provider.provider_id,
                model=provider.model_name,
                device=provider.device,
                precision=provider.precision,
                dataset_version=self.settings.dataset_version,
                benchmark_version=self.settings.benchmark_version,
                total_samples=len(samples),
                successful_samples=0,
                failed_samples=len(samples),
                overall_wer=1.0,
                overall_cer=1.0,
                age_accuracy=0.0,
                income_accuracy=0.0,
                district_accuracy=0.0,
                negation_accuracy=0.0,
                government_term_accuracy=0.0,
                all_critical_entities_accuracy=0.0,
                avg_inference_ms=0.0,
                avg_rtf=0.0,
                model_load_time_seconds=0.0,
                categories={},
                total_critical_failures=0,
            )
            report_lines = [
                f"# JanSetu — STT Benchmark Report: {provider.provider_id.upper()} ({provider.model_name})",
                "",
                "**Status**: `PROVIDER_UNAVAILABLE`  ",
                f"**Diagnostics**: `{load_err}`  ",
                "",
                "> [!WARNING]",
                "> This provider could not be evaluated because model weights or dependencies are unavailable or not cached locally.",
            ]
            (run_out_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
            with open(run_out_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(unavail_summary.model_dump(mode="json"), f, indent=2)
            with open(run_out_dir / "critical_failures.json", "w", encoding="utf-8") as f:
                json.dump([], f)
            with open(run_out_dir / "samples.jsonl", "w", encoding="utf-8") as f:
                pass
            return unavail_summary, []

        ram_after, vram = self._measure_resources()
        if ram_after is not None and ram_before is not None:
            ram_used_mb = max(round(ram_after - ram_before, 2), ram_after)
        else:
            ram_used_mb = ram_after

        # 2. Iterate Samples
        sample_results: List[SampleResult] = []
        is_first = True

        for idx, sample in enumerate(samples):
            audio_path = dataset_path / sample.audio_file
            logger.debug(f"[{idx+1}/{len(samples)}] Processing sample {sample.id}...")

            try:
                # Transcribe with language hint if configured
                lang_hint = self.settings.language_hint if sample.language == "hi" else None
                t0_inf = time.perf_counter()
                stt_res = provider.transcribe(audio_path, language_hint=lang_hint)
                inf_time_ms = (time.perf_counter() - t0_inf) * 1000.0

                if is_first:
                    logger.info(f"Cold inference latency ({sample.id}): {inf_time_ms:.1f}ms")
                    is_first = False

                # Evaluate sample
                eval_res = BenchmarkMetricsEvaluator.evaluate_sample(sample, stt_res)
                sample_results.append(eval_res)

            except Exception as sample_err:
                logger.warning(f"Error processing sample {sample.id}: {sample_err}")
                duration = 0.0
                try:
                    duration, _, _ = AudioNormalizer.get_audio_info(audio_path)
                except Exception:
                    pass

                # Record error sample result without terminating
                failed_res = SampleResult(
                    sample_id=sample.id,
                    audio_duration_seconds=round(duration, 2),
                    inference_ms=0.0,
                    real_time_factor=0.0,
                    reference_raw=sample.reference,
                    prediction_raw="",
                    reference_normalized="",
                    prediction_normalized="",
                    wer=1.0,
                    cer=1.0,
                    category=sample.category.value,
                    noise_level=sample.noise_level.value,
                    all_critical_entities_correct=False,
                    has_critical_failure=True,
                    error=str(sample_err),
                )
                sample_results.append(failed_res)

        # 3. Aggregate Results
        summary, critical_failures = BenchmarkMetricsEvaluator.aggregate_results(
            run_id=run_id,
            provider=provider.provider_id,
            model=provider.model_name,
            device=provider.device,
            precision=provider.precision,
            dataset_version=self.settings.dataset_version,
            benchmark_version=self.settings.benchmark_version,
            sample_results=sample_results,
            model_load_time_seconds=load_time_sec,
            ram_usage_mb=ram_used_mb,
            vram_usage_mb=vram,
        )

        # 4. Save Artifacts
        self._save_artifacts(run_out_dir, summary, sample_results, critical_failures)

        # 5. Unload Provider
        try:
            provider.unload()
        except Exception as unload_err:
            logger.warning(f"Error unloading provider {provider.provider_id}: {unload_err}")

        logger.info(
            f"Completed Run {run_id}: Samples={summary.total_samples}, "
            f"WER={summary.overall_wer:.4f}, CER={summary.overall_cer:.4f}, "
            f"AgeAcc={summary.age_accuracy:.2%}, IncomeAcc={summary.income_accuracy:.2%}, "
            f"DistAcc={summary.district_accuracy:.2%}, RTF={summary.avg_rtf:.3f}"
        )

        return summary, critical_failures

    def _save_artifacts(
        self,
        out_dir: Path,
        summary: BenchmarkSummary,
        samples: List[SampleResult],
        critical_failures: List[CriticalFailureItem],
    ) -> None:
        """Saves summary.json, samples.jsonl, critical_failures.json, and report.md."""
        # A. summary.json
        with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        # B. samples.jsonl
        with open(out_dir / "samples.jsonl", "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s.model_dump(mode="json"), ensure_ascii=False) + "\n")

        # C. critical_failures.json
        with open(out_dir / "critical_failures.json", "w", encoding="utf-8") as f:
            json.dump(
                [cf.model_dump(mode="json") for cf in critical_failures],
                f,
                indent=2,
                ensure_ascii=False,
            )

        # D. report.md
        report_md = self._generate_markdown_report(summary, critical_failures)
        with open(out_dir / "report.md", "w", encoding="utf-8") as f:
            f.write(report_md)

        logger.info(f"Persisted benchmark artifacts in: {out_dir}")

    def _generate_markdown_report(
        self,
        summary: BenchmarkSummary,
        critical_failures: List[CriticalFailureItem],
    ) -> str:
        """Generates comprehensive human-readable Markdown benchmark report."""
        lines = [
            f"# JanSetu — STT Benchmark Report: {summary.provider.upper()} ({summary.model})",
            "",
            f"**Run ID**: `{summary.benchmark_run_id}`  ",
            f"**Timestamp**: `{summary.timestamp.isoformat()}`  ",
            f"**Device**: `{summary.device}` | **Precision**: `{summary.precision}`  ",
            f"**Dataset Version**: `{summary.dataset_version}` | **Benchmark Engine**: `v{summary.benchmark_version}`  ",
            "",
            "---",
            "",
            "## 1. Executive Summary & Accuracy Overview",
            "",
            "| Metric | Value | Target / Notes |",
            "| :--- | :--- | :--- |",
            f"| **Total Samples** | `{summary.total_samples}` | Successful: {summary.successful_samples}, Failed: {summary.failed_samples} |",
            f"| **Overall WER** | `{summary.overall_wer:.4f}` ({summary.overall_wer*100:.1f}%) | Word Error Rate (Normalized) |",
            f"| **Overall CER** | `{summary.overall_cer:.4f}` ({summary.overall_cer*100:.1f}%) | Character Error Rate (Normalized) |",
            f"| **Age Accuracy** | `{summary.age_accuracy:.2%}` | Eligibility Critical (e.g. 62 vs 26) |",
            f"| **Income Accuracy** | `{summary.income_accuracy:.2%}` | Eligibility Critical (e.g. 1.5L vs 2.5L) |",
            f"| **District Accuracy** | `{summary.district_accuracy:.2%}` | Rajasthan 50-District Registry |",
            f"| **Negation Accuracy** | `{summary.negation_accuracy:.2%}` | BPL / Assertion Flip Detection |",
            f"| **Govt Term Accuracy** | `{summary.government_term_accuracy:.2%}` | Jan Aadhaar, e-Mitra, SSO, etc. |",
            f"| **All Critical Fields Correct** | `{summary.all_critical_entities_accuracy:.2%}` | Utterances with 100% Correct Entities |",
            f"| **Total Critical Failures** | `{summary.total_critical_failures}` | Actionable Breaches |",
            "",
            "---",
            "",
            "## 2. Latency & Hardware Resource Footprint",
            "",
            "| Metric | Measurement |",
            "| :--- | :--- |",
            f"| **Model Load Time** | `{summary.model_load_time_seconds:.2f} s` |",
            f"| **Average Inference Latency** | `{summary.avg_inference_ms:.1f} ms` |",
            f"| **Average Real-Time Factor (RTF)** | `{summary.avg_rtf:.4f}` (lower is better, <1.0 = faster than real-time) |",
            f"| **RAM Footprint** | `{summary.ram_usage_mb} MB` |",
            f"| **VRAM Footprint** | `{summary.vram_usage_mb if summary.vram_usage_mb is not None else 'N/A (CPU)'}` |",
            "",
            "---",
            "",
            "## 3. Category-by-Category Performance Breakdown",
            "",
            "| Category | Samples | Avg WER | Avg CER | Latency (ms) | RTF | All Entities Acc | Critical Fails |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for cat_name, c in sorted(summary.categories.items()):
            lines.append(
                f"| `{cat_name}` | {c.sample_count} | {c.avg_wer:.4f} | {c.avg_cer:.4f} | "
                f"{c.avg_inference_ms:.1f} ms | {c.avg_rtf:.3f} | {c.all_entities_accuracy:.1%} | {c.critical_failures_count} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 4. Critical Eligibility Failures Detail",
            "",
        ])

        if not critical_failures:
            lines.append("✅ **Zero critical eligibility failures detected in this benchmark run!**")
        else:
            lines.append(f"⚠️ **Found {len(critical_failures)} critical eligibility errors:**\n")
            lines.append("| Sample ID | Category | Field | Expected | Predicted | Reference Text | Predicted Text |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for cf in critical_failures[:25]:  # show up to 25
                ref_escaped = cf.reference_text.replace("|", "/")
                pred_escaped = cf.predicted_text.replace("|", "/")
                lines.append(
                    f"| `{cf.sample_id}` | `{cf.category}` | `{cf.field_name}` | `{cf.expected_value}` | "
                    f"`{cf.predicted_value}` | {ref_escaped} | {pred_escaped} |"
                )

        return "\n".join(lines)


def main():
    """CLI entry point for running STT benchmarks."""
    parser = argparse.ArgumentParser(description="JanSetu - Local STT Benchmark Suite")
    parser.add_argument(
        "--provider",
        choices=["whisper", "indic_asr", "mock", "all"],
        default="all",
        help="STT provider to benchmark (default: all)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name or checkpoint (defaults to provider standard)",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Inference device (default: cpu)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("tests/stt_benchmark"),
        help="Path to dataset directory containing manifest.json and audio/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("storage/benchmarks/stt"),
        help="Directory to save benchmark output artifacts",
    )
    parser.add_argument(
        "--initial-prompt",
        default=None,
        help="Initial prompt for biasing STT vocabulary/script (e.g. Devanagari domain prompt)",
    )
    parser.add_argument(
        "--language-hint",
        default="hi",
        help="Language hint for transcription (default: hi, 'none' for auto-detection)",
    )

    args = parser.parse_args()
    settings = get_stt_settings()
    settings.dataset_path = args.dataset
    settings.storage_path = args.output
    settings.device = args.device
    if args.language_hint.lower() in ("none", "auto", ""):
        settings.language_hint = None
    else:
        settings.language_hint = args.language_hint

    runner = STTBenchmarkRunner(settings)
    samples = runner.load_manifest(args.dataset)

    providers_to_run: List[SpeechToTextProvider] = []

    if args.provider in ["whisper", "all"]:
        w_model = args.model or settings.whisper_model
        providers_to_run.append(
            WhisperSTTProvider(
                model_name=w_model,
                device=args.device,
                initial_prompt=args.initial_prompt,
            )
        )

    if args.provider in ["indic_asr", "all"]:
        i_model = args.model or settings.indic_asr_model
        providers_to_run.append(
            IndicASRSTTProvider(model_name=i_model, device=args.device)
        )

    if args.provider == "mock":
        providers_to_run.append(
            MockSTTProvider(model_name="mock-v1", device=args.device)
        )

    for p in providers_to_run:
        if not p.is_available():
            logger.warning(
                f"Provider '{p.provider_id}' is UNAVAILABLE in this environment. Skipping."
            )
            continue

        try:
            runner.run_provider_benchmark(
                provider=p,
                samples=samples,
                dataset_path=args.dataset,
                output_dir=args.output,
            )
        except Exception as e:
            logger.error(f"Failed benchmark run for provider '{p.provider_id}': {e}")


if __name__ == "__main__":
    main()
