"""
JanSetu - Day 22: Speech-to-Text Benchmark Metrics Engine.

Computes:
- Word Error Rate (WER) using Levenshtein distance on normalized word tokens
- Character Error Rate (CER) using Levenshtein distance on normalized character tokens
- Real-Time Factor (RTF = inference_time / audio_duration)
- Domain-specific critical entity accuracy (Age, Income, District, Negation, Terms)
- Aggregated benchmark run summaries and actionable critical failure lists
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.stt.entity_metrics import EntityMetricsExtractor
from app.stt.schemas import (
    BenchmarkSample,
    BenchmarkSummary,
    CategoryMetricSummary,
    CriticalFailureItem,
    SampleResult,
    STTResult,
)
from app.stt.transcript_normalizer import TranscriptNormalizer


def levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> int:
    """
    Computes standard Levenshtein edit distance (insertions, deletions, substitutions)
    between two sequences using dynamic programming with O(min(N, M)) memory.
    """
    n, m = len(seq1), len(seq2)
    if n == 0:
        return m
    if m == 0:
        return n

    # Make seq2 the shorter sequence for memory efficiency
    if n < m:
        seq1, seq2 = seq2, seq1
        n, m = m, n

    current_row = list(range(m + 1))
    for i in range(1, n + 1):
        previous_row = current_row
        current_row = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            current_row[j] = min(
                previous_row[j] + 1,       # deletion
                current_row[j - 1] + 1,    # insertion
                previous_row[j - 1] + cost # substitution
            )

    return current_row[m]


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculates Word Error Rate (WER) between normalized reference and hypothesis strings.
    WER = (S + D + I) / N
    """
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    edit_distance = levenshtein_distance(ref_words, hyp_words)
    return float(edit_distance / len(ref_words))


def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Calculates Character Error Rate (CER) between normalized reference and hypothesis.
    CER = (S + D + I) / N_chars
    """
    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))

    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0

    edit_distance = levenshtein_distance(ref_chars, hyp_chars)
    return float(edit_distance / len(ref_chars))


class BenchmarkMetricsEvaluator:
    """Evaluates individual samples and aggregates overall benchmark metrics."""

    @classmethod
    def evaluate_sample(
        cls,
        sample: BenchmarkSample,
        stt_result: STTResult,
    ) -> SampleResult:
        """
        Evaluates a single sample:
        - Stores raw reference and raw prediction immutably
        - Normalizes transcripts for WER/CER calculation
        - Evaluates critical entity targets (age, income, district, negation, etc.)
        - Calculates RTF and latency metrics
        """
        raw_ref = sample.reference
        raw_pred = stt_result.raw_text

        # 1. Normalize for distance metrics
        norm_ref = TranscriptNormalizer.normalize_for_metrics(raw_ref)
        norm_pred = TranscriptNormalizer.normalize_for_metrics(raw_pred)

        # 2. Compute literal transcription metrics
        wer = calculate_wer(norm_ref, norm_pred)
        cer = calculate_cer(norm_ref, norm_pred)

        # 3. Compute Real-Time Factor
        audio_dur = max(stt_result.duration_seconds, 0.01)
        inference_sec = stt_result.inference_ms / 1000.0
        rtf = round(inference_sec / audio_dur, 4)

        # 4. Evaluate task-semantic critical entities
        crit_results, all_correct, has_critical = EntityMetricsExtractor.evaluate_sample(
            raw_pred, sample.entities
        )

        return SampleResult(
            sample_id=sample.id,
            audio_duration_seconds=round(stt_result.duration_seconds, 2),
            inference_ms=round(stt_result.inference_ms, 2),
            real_time_factor=rtf,
            reference_raw=raw_ref,
            prediction_raw=raw_pred,
            reference_normalized=norm_ref,
            prediction_normalized=norm_pred,
            wer=round(wer, 4),
            cer=round(cer, 4),
            category=sample.category.value,
            noise_level=sample.noise_level.value,
            critical_entities=crit_results,
            all_critical_entities_correct=all_correct,
            has_critical_failure=has_critical,
        )

    @classmethod
    def aggregate_results(
        cls,
        run_id: str,
        provider: str,
        model: str,
        device: str,
        precision: str,
        dataset_version: str,
        benchmark_version: str,
        sample_results: List[SampleResult],
        model_load_time_seconds: float = 0.0,
        ram_usage_mb: Optional[float] = None,
        vram_usage_mb: Optional[float] = None,
        disk_footprint_mb: Optional[float] = None,
    ) -> Tuple[BenchmarkSummary, List[CriticalFailureItem]]:
        """
        Aggregates sample results into comprehensive BenchmarkSummary
        and compiles list of actionable CriticalFailureItem records.
        """
        total = len(sample_results)
        successful = sum(1 for s in sample_results if not s.error)
        failed = total - successful

        if total == 0:
            empty_summary = BenchmarkSummary(
                benchmark_run_id=run_id,
                provider=provider,
                model=model,
                device=device,
                precision=precision,
                dataset_version=dataset_version,
                benchmark_version=benchmark_version,
                timestamp=datetime.now(timezone.utc),
                total_samples=0,
                successful_samples=0,
                failed_samples=0,
                overall_wer=0.0,
                overall_cer=0.0,
                avg_inference_ms=0.0,
                avg_rtf=0.0,
                age_accuracy=0.0,
                income_accuracy=0.0,
                district_accuracy=0.0,
                negation_accuracy=0.0,
                government_term_accuracy=0.0,
                all_critical_entities_accuracy=0.0,
                total_critical_failures=0,
            )
            return empty_summary, []

        overall_wer = sum(s.wer for s in sample_results) / total
        overall_cer = sum(s.cer for s in sample_results) / total
        avg_inf_ms = sum(s.inference_ms for s in sample_results) / total
        avg_rtf = sum(s.real_time_factor for s in sample_results) / total

        # Critical Entity Accuracies
        age_samples = [s for s in sample_results if "age" in s.critical_entities]
        age_acc = (
            sum(1 for s in age_samples if s.critical_entities["age"].is_correct) / len(age_samples)
            if age_samples else 1.0
        )

        income_samples = [s for s in sample_results if "family_income" in s.critical_entities]
        income_acc = (
            sum(1 for s in income_samples if s.critical_entities["family_income"].is_correct) / len(income_samples)
            if income_samples else 1.0
        )

        dist_samples = [s for s in sample_results if "district" in s.critical_entities]
        dist_acc = (
            sum(1 for s in dist_samples if s.critical_entities["district"].is_correct) / len(dist_samples)
            if dist_samples else 1.0
        )

        neg_samples = [s for s in sample_results if "negation" in s.critical_entities]
        neg_acc = (
            sum(1 for s in neg_samples if s.critical_entities["negation"].is_correct) / len(neg_samples)
            if neg_samples else 1.0
        )

        term_samples = [s for s in sample_results if "scheme_name" in s.critical_entities]
        term_acc = (
            sum(1 for s in term_samples if s.critical_entities["scheme_name"].is_correct) / len(term_samples)
            if term_samples else 1.0
        )

        all_crit_acc = sum(1 for s in sample_results if s.all_critical_entities_correct) / total

        # Collect Critical Failures
        critical_failures: List[CriticalFailureItem] = []
        for s in sample_results:
            for fname, fmatch in s.critical_entities.items():
                if fmatch.is_critical_failure:
                    critical_failures.append(
                        CriticalFailureItem(
                            sample_id=s.sample_id,
                            category=s.category,
                            field_name=fname,
                            expected_value=fmatch.expected,
                            predicted_value=fmatch.predicted,
                            reference_text=s.reference_raw,
                            predicted_text=s.prediction_raw,
                            reason=fmatch.details or f"Mismatch in {fname}",
                        )
                    )

        # Breakdown by Category
        by_category: Dict[str, List[SampleResult]] = defaultdict(list)
        for s in sample_results:
            by_category[s.category].append(s)

        cat_summaries: Dict[str, CategoryMetricSummary] = {}
        for cat_name, cat_items in by_category.items():
            c_tot = len(cat_items)
            c_wer = sum(c.wer for c in cat_items) / c_tot
            c_cer = sum(c.cer for c in cat_items) / c_tot
            c_inf = sum(c.inference_ms for c in cat_items) / c_tot
            c_rtf = sum(c.real_time_factor for c in cat_items) / c_tot
            c_ent = sum(1 for c in cat_items if c.all_critical_entities_correct) / c_tot
            c_fails = sum(1 for c in cat_items if c.has_critical_failure)

            cat_summaries[cat_name] = CategoryMetricSummary(
                category=cat_name,
                sample_count=c_tot,
                avg_wer=round(c_wer, 4),
                avg_cer=round(c_cer, 4),
                avg_inference_ms=round(c_inf, 2),
                avg_rtf=round(c_rtf, 4),
                all_entities_accuracy=round(c_ent, 4),
                critical_failures_count=c_fails,
            )

        summary = BenchmarkSummary(
            benchmark_run_id=run_id,
            provider=provider,
            model=model,
            device=device,
            precision=precision,
            dataset_version=dataset_version,
            benchmark_version=benchmark_version,
            timestamp=datetime.now(timezone.utc),
            total_samples=total,
            successful_samples=successful,
            failed_samples=failed,
            overall_wer=round(overall_wer, 4),
            overall_cer=round(overall_cer, 4),
            avg_inference_ms=round(avg_inf_ms, 2),
            avg_rtf=round(avg_rtf, 4),
            age_accuracy=round(age_acc, 4),
            income_accuracy=round(income_acc, 4),
            district_accuracy=round(dist_acc, 4),
            negation_accuracy=round(neg_acc, 4),
            government_term_accuracy=round(term_acc, 4),
            all_critical_entities_accuracy=round(all_crit_acc, 4),
            total_critical_failures=len(critical_failures),
            categories=cat_summaries,
            model_load_time_seconds=round(model_load_time_seconds, 3),
            ram_usage_mb=ram_usage_mb,
            vram_usage_mb=vram_usage_mb,
            disk_footprint_mb=disk_footprint_mb,
        )

        return summary, critical_failures
