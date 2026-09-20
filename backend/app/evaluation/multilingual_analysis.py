"""
JanSetu - Day 31: Multilingual Retrieval Analysis & Slice Performance Evaluator.

Evaluates performance across linguistic and query intent dimensions:
- Independent metrics for Hindi, English, Hinglish, and Dialect
- Query-type breakdown: exact-name, benefit-driven, beneficiary-driven, problem-driven, profile-only
- Dialect status reporting (e.g. INSUFFICIENT_DIALECT_SEARCH_COVERAGE)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LanguageSliceMetrics(BaseModel):
    """Retrieval and ranking metrics for a specific linguistic slice."""
    language: str
    total_cases: int = 0
    relevant_queries: int = 0
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0
    avg_similarity: float = 0.0
    status_note: Optional[str] = None


class QueryTypeSliceMetrics(BaseModel):
    """Retrieval and ranking metrics for a specific query intent type."""
    query_type: str
    total_cases: int = 0
    recall_at_5: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0


class MultilingualMetrics(BaseModel):
    """Comprehensive multilingual and query intent analysis."""
    hindi: LanguageSliceMetrics = Field(default_factory=lambda: LanguageSliceMetrics(language="hi"))
    english: LanguageSliceMetrics = Field(default_factory=lambda: LanguageSliceMetrics(language="en"))
    hinglish: LanguageSliceMetrics = Field(default_factory=lambda: LanguageSliceMetrics(language="hi-Latn"))
    dialect: LanguageSliceMetrics = Field(default_factory=lambda: LanguageSliceMetrics(language="dialect"))

    # Intent breakdown
    query_types: Dict[str, QueryTypeSliceMetrics] = Field(default_factory=dict)


class MultilingualAnalyzer:
    """Analyzes discovery search results across languages and query formats."""

    @classmethod
    def analyze(cls, case_evaluations: List[Dict[str, Any]]) -> MultilingualMetrics:
        """Computes stratified multilingual and intent metrics."""
        metrics = MultilingualMetrics()

        slices = {
            "hi": [],
            "en": [],
            "hi-Latn": [],
            "dialect": [],
        }

        query_type_slices: Dict[str, List[Dict[str, Any]]] = {}

        for case in case_evaluations:
            lang = case.get("language", "hi")
            tags = [t.upper() for t in case.get("tags", [])]

            # Classify language
            if "HINGLISH" in tags or lang in ("hi-Latn", "hinglish", "en-hi"):
                slices["hi-Latn"].append(case)
            elif "DIALECT" in tags or "MARWARI" in tags or "MEWARI" in tags:
                slices["dialect"].append(case)
            elif lang == "en" or "ENGLISH" in tags:
                slices["en"].append(case)
            else:
                slices["hi"].append(case)

            # Classify query intent
            qtype = case.get("query_type", "NATURAL")
            if case.get("query") is None or "NO_QUERY" in tags or "PROFILE_ONLY" in tags:
                qtype = "PROFILE_ONLY"
            elif "EXACT_NAME" in tags:
                qtype = "EXACT_NAME"
            elif "BENEFIT_DRIVEN" in tags:
                qtype = "BENEFIT_DRIVEN"
            elif "BENEFICIARY_DRIVEN" in tags:
                qtype = "BENEFICIARY_DRIVEN"
            elif "PROBLEM_DRIVEN" in tags:
                qtype = "PROBLEM_DRIVEN"

            query_type_slices.setdefault(qtype, []).append(case)

        # Compute language slice metrics
        metrics.hindi = cls._compute_slice("hi", slices["hi"])
        metrics.english = cls._compute_slice("en", slices["en"])
        metrics.hinglish = cls._compute_slice("hi-Latn", slices["hi-Latn"])

        # Dialect slice: check sample sufficiency
        if len(slices["dialect"]) < 3:
            metrics.dialect = cls._compute_slice("dialect", slices["dialect"])
            metrics.dialect.status_note = "INSUFFICIENT_DIALECT_SEARCH_COVERAGE"
        else:
            metrics.dialect = cls._compute_slice("dialect", slices["dialect"])

        # Compute query type metrics
        for qt, cases in query_type_slices.items():
            qt_slice = cls._compute_slice(qt, cases)
            metrics.query_types[qt] = QueryTypeSliceMetrics(
                query_type=qt,
                total_cases=qt_slice.total_cases,
                recall_at_5=qt_slice.recall_at_5,
                precision_at_5=qt_slice.precision_at_5,
                mrr=qt_slice.mrr,
            )

        return metrics

    @classmethod
    def _compute_slice(cls, name: str, cases: List[Dict[str, Any]]) -> LanguageSliceMetrics:
        slice_metric = LanguageSliceMetrics(language=name, total_cases=len(cases))
        if not cases:
            return slice_metric

        relevant_cases = [c for c in cases if not c.get("expected_empty", False)]
        slice_metric.relevant_queries = len(relevant_cases)
        if not relevant_cases:
            return slice_metric

        r1, r3, r5, r10 = [], [], [], []
        p5 = []
        rr = []
        sims = []

        for c in relevant_cases:
            rk = c.get("ranking_evaluation", {})
            recalls = rk.get("recalls", {})
            precisions = rk.get("precisions", {})

            r1.append(recalls.get(1, 0.0))
            r3.append(recalls.get(3, 0.0))
            r5.append(recalls.get(5, 0.0))
            r10.append(recalls.get(10, 0.0))

            p5.append(precisions.get(5, 0.0))
            rr.append(rk.get("rr", 0.0))

            sim = c.get("target_semantic_similarity")
            if sim is not None:
                sims.append(sim)

        n = len(relevant_cases)
        slice_metric.recall_at_1 = round(sum(r1) / n, 4)
        slice_metric.recall_at_3 = round(sum(r3) / n, 4)
        slice_metric.recall_at_5 = round(sum(r5) / n, 4)
        slice_metric.recall_at_10 = round(sum(r10) / n, 4)
        slice_metric.precision_at_5 = round(sum(p5) / n, 4)
        slice_metric.mrr = round(sum(rr) / n, 4)
        slice_metric.avg_similarity = round(sum(sims) / len(sims), 4) if sims else 0.0

        return slice_metric
