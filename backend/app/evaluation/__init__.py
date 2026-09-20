"""
YojanSetu - Day 29: Evaluation Subsystem Package.
"""

from app.evaluation.evidence_metrics import EvidenceGroundingEvaluator
from app.evaluation.extraction_metrics import ExtractionMetricAggregator
from app.evaluation.extraction_runner import ExtractionBenchmarkRunner
from app.evaluation.failure_analysis import FailureAnalyzer
from app.evaluation.matching import ExtractedFactItem, FactMatcher
from app.evaluation.reporting import BenchmarkReportGenerator
from app.evaluation.rule_metrics import CanonicalRuleComparator, RuleNode
from app.evaluation.schemas import (
    BenchmarkRunManifest,
    BenchmarkSummary,
    CaseEvaluationResult,
    FactEvaluation,
    FailureCode,
    FailureSeverity,
    MatchResult,
    PipelineStage,
)

__all__ = [
    "EvidenceGroundingEvaluator",
    "ExtractionBenchmarkRunner",
    "ExtractionMetricAggregator",
    "FailureAnalyzer",
    "FactMatcher",
    "ExtractedFactItem",
    "BenchmarkReportGenerator",
    "CanonicalRuleComparator",
    "RuleNode",
    "BenchmarkRunManifest",
    "BenchmarkSummary",
    "CaseEvaluationResult",
    "FactEvaluation",
    "FailureCode",
    "FailureSeverity",
    "MatchResult",
    "PipelineStage",
]
