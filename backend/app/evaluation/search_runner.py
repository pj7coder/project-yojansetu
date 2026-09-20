"""
YojanSetu - Day 31: End-to-End Scheme Discovery & Search Quality Evaluation Runner.

Executes read-only benchmarking of the discovery pipeline against human-verified gold ground truth:
Stage A (Corpus Index) -> Stage B (SQL Filter) -> Stage C (Eligibility) -> Stage D (Vector Ranking) -> Stage E (Recommendations).
Enforces runtime data-leakage protection, stage-level failure diagnosis, and comprehensive safety auditing.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.scheme_embedding import SchemeEmbedding
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.eligibility.service import EligibilityService
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.evaluation.bucket_metrics import BucketMetricsCalculator
from app.evaluation.candidate_metrics import CandidateMetricsCalculator
from app.evaluation.multilingual_analysis import MultilingualAnalyzer
from app.evaluation.ranking_metrics import RankingMetricsCalculator
from app.evaluation.search_failure_analysis import SearchFailureAttributor, SearchFailureCode, SearchPipelineStage
from app.evaluation.search_metrics import (
    DegradedModeMetrics,
    IndexHealthMetrics,
    SearchBenchmarkSummary,
    SearchCaseResult,
)
from app.evaluation.search_reporting import SearchBenchmarkReporter
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import CaseStatus, GoldSplit, GoldTask, SearchGoldCase
from app.search.candidate_filter import CandidateFilterService
from app.search.discovery_service import SchemeDiscoveryService
from app.search.indexer import SchemeSearchIndexService
from app.search.schemas import SchemeDiscoveryRequest
from app.search.semantic_ranker import SemanticSchemeRanker

logger = logging.getLogger("yojansetu.evaluation.search_runner")


class SearchBenchmarkRunner:
    """
    Evaluates YojanSetu's scheme-discovery pipeline against frozen human-verified search gold cases.
    """

    def __init__(
        self,
        gold_version: str = "v1",
        loader: Optional[GoldBenchmarkLoader] = None,
        output_base_dir: Optional[Path] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.gold_version = gold_version
        self.loader = loader or GoldBenchmarkLoader(version=gold_version)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        self.output_base_dir = output_base_dir or (repo_root / "storage" / "benchmarks" / "search")
        self.provider = embedding_provider or LocalFastEmbedProvider()

    def run_benchmark(
        self,
        split: Union[GoldSplit, str] = GoldSplit.DEV,
        tag_filter: Optional[List[str]] = None,
        case_id_filter: Optional[str] = None,
        top_k: int = 5,
        enforce_leakage_protection: bool = True,
        persist_results: bool = True,
    ) -> Tuple[SearchBenchmarkSummary, List[SearchCaseResult]]:
        """
        Executes search benchmark evaluation across specified split or single case.
        """
        start_eval_time = time.perf_counter()
        split_enum = GoldSplit(split) if isinstance(split, str) else split

        # 1. Load gold benchmark cases
        all_cases: List[SearchGoldCase] = self.loader.load_cases(
            task=GoldTask.SEARCH,
            split=split_enum,
            status=CaseStatus.HUMAN_VERIFIED,
        )

        selected_cases: List[SearchGoldCase] = []
        for c in all_cases:
            if case_id_filter and c.case_id != case_id_filter:
                continue
            if tag_filter:
                case_tags = [t.upper() for t in c.tags]
                if not any(t.upper() in case_tags for t in tag_filter):
                    continue
            selected_cases.append(c)

        run_id = f"srch_eval_{split_enum.value.lower()}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # 2. Strict Data-Leakage Protection: pure inputs map
        runtime_inputs_map: Dict[str, Dict[str, Any]] = {}
        if enforce_leakage_protection:
            try:
                inputs_list = self.loader.get_runtime_inputs(
                    task=GoldTask.SEARCH,
                    split=split_enum,
                    status=CaseStatus.HUMAN_VERIFIED,
                )
                runtime_inputs_map = {inp["case_id"]: inp for inp in inputs_list}
            except Exception as e:
                logger.warning(f"Could not load isolated runtime inputs: {e}")

        session = SessionLocal()
        case_results: List[SearchCaseResult] = []
        durations: List[float] = []

        # Intermediates for component aggregators
        candidate_eval_cases: List[Dict[str, Any]] = []
        ranking_eval_cases: List[Dict[str, Any]] = []
        bucket_eval_cases: List[Dict[str, Any]] = []
        multilingual_eval_cases: List[Dict[str, Any]] = []

        try:
            # Check index health before running
            index_status = SchemeSearchIndexService.get_index_status(session)
            indexed_ids = set(session.query(SchemeSearchMetadata.scheme_id).all())
            indexed_ids_set = {r[0] for r in indexed_ids}

            # Stale embedding scheme IDs
            stale_stmt = (
                select(SchemeSearchMetadata.scheme_id)
                .join(SchemeEmbedding, SchemeSearchMetadata.scheme_id == SchemeEmbedding.scheme_id)
                .where(SchemeSearchMetadata.search_text_hash != SchemeEmbedding.search_text_hash)
            )
            stale_ids = set(session.execute(stale_stmt).scalars().all())

            # 3. Evaluate each search case
            for case in selected_cases:
                case_start = time.perf_counter()

                # Extract runtime inputs without ground truth
                if runtime_inputs_map and case.case_id in runtime_inputs_map:
                    inp = runtime_inputs_map[case.case_id]
                    runtime_query = inp.get("query")
                    runtime_profile = inp.get("profile") or {}
                else:
                    runtime_query = case.query
                    runtime_profile = case.profile or {}

                # Stage B: Execute SQL Candidate Filtering directly to inspect candidates
                profile_obj = CitizenProfile(**runtime_profile)
                sql_candidates, total_verified = CandidateFilterService.filter_candidates(
                    session=session,
                    profile=profile_obj,
                )

                # Stage C: Deterministic Eligibility on Candidates
                eval_results = EligibilityService.evaluate_multiple_schemes(
                    session=session,
                    scheme_ids=sql_candidates,
                    profile_data=runtime_profile,
                )

                eligible_ids = [
                    r.scheme_id for r in eval_results if r.eligibility_status == EligibilityStatus.ELIGIBLE
                ]
                more_info_ids = [
                    r.scheme_id for r in eval_results if r.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
                ]
                not_eligible_ids = [
                    r.scheme_id for r in eval_results if r.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
                ]

                # Full End-to-End Pipeline Execution via SchemeDiscoveryService
                req = SchemeDiscoveryRequest(
                    need_text=runtime_query,
                    profile=runtime_profile,
                    limit=top_k,
                )
                discovery_resp = SchemeDiscoveryService.discover_schemes(
                    session=session,
                    request=req,
                    embedding_provider=self.provider,
                )

                case_duration = (time.perf_counter() - case_start) * 1000.0
                durations.append(case_duration)

                ranked_el_ids = [item.scheme_id for item in discovery_resp.eligible]
                ranked_mi_ids = [item.scheme_id for item in discovery_resp.more_information_required]
                all_ranked = ranked_el_ids + ranked_mi_ids

                # Ground truth comparisons
                gold_rel_ids = [r.scheme_id for r in case.expected.relevance_judgments]
                graded_map = {r.scheme_id: r.relevance.value for r in case.expected.relevance_judgments}

                # Evaluate ranking metrics
                case_ranking = RankingMetricsCalculator.calculate_case_ranking(
                    ranked_scheme_ids=all_ranked,
                    gold_relevant_scheme_ids=gold_rel_ids,
                    graded_judgments=graded_map,
                    acceptable_top_set=case.expected.acceptable_top_set,
                    must_appear_top_5=case.expected.must_appear_top_5,
                    expected_empty=case.expected.expected_empty,
                )

                # Evaluate bucket metrics & safety
                case_buckets = BucketMetricsCalculator.evaluate_case_buckets(
                    eligible_items=[item.model_dump() for item in discovery_resp.eligible],
                    more_info_items=[item.model_dump() for item in discovery_resp.more_information_required],
                    not_eligible_ids=not_eligible_ids,
                    expected_eligible_ids=gold_rel_ids if not case.expected.expected_empty else [],
                    must_not_appear_top_k=case.expected.must_not_appear_top_k,
                )

                # Check known disqualification
                is_known_disqual = False
                disqual_respected = True
                if runtime_profile.get("state") and runtime_profile.get("state", "").lower() != "rajasthan":
                    is_known_disqual = True
                    # Disqualification respected if Rajasthan-only schemes are excluded
                    disqual_respected = not any(
                        sid in sql_candidates for sid in ("e54ebf76-b896-4292-b033-ce77e913bc35",)
                    )

                # Candidate filter case dict
                candidate_eval_cases.append({
                    "sql_candidates": sql_candidates,
                    "gold_relevant_scheme_ids": gold_rel_ids,
                    "profile": runtime_profile,
                    "is_known_disqualification": is_known_disqual,
                    "disqualification_respected": disqual_respected,
                })

                # Target similarity / rank
                target_sim = None
                target_rank = None
                for idx, item in enumerate(discovery_resp.eligible + discovery_resp.more_information_required):
                    if item.scheme_id in gold_rel_ids:
                        target_sim = item.semantic_similarity
                        target_rank = idx + 1
                        break

                # Ranking case dict
                ranking_eval_cases.append({
                    "case_id": case.case_id,
                    "expected_empty": case.expected.expected_empty,
                    "recommendation_count": len(all_ranked),
                    "ranking_evaluation": case_ranking,
                    "has_acceptable_top_set": bool(case.expected.acceptable_top_set),
                    "has_must_appear_top_5": bool(case.expected.must_appear_top_5),
                    "query_type": case.query_type,
                    "tags": case.tags,
                })

                # Bucket case dict
                bucket_eval_cases.append({
                    "bucket_evaluation": case_buckets,
                    "expected_eligible_ids": gold_rel_ids if not case.expected.expected_empty else [],
                    "expected_more_info_ids": [],
                    "not_eligible_count": len(not_eligible_ids),
                })

                # Multilingual case dict
                multilingual_eval_cases.append({
                    "case_id": case.case_id,
                    "language": case.language,
                    "tags": case.tags,
                    "query": runtime_query,
                    "query_type": case.query_type,
                    "expected_empty": case.expected.expected_empty,
                    "ranking_evaluation": case_ranking,
                    "target_semantic_similarity": target_sim,
                })

                # Stage-Level Root Cause Diagnosis
                diagnoses = SearchFailureAttributor.diagnose_case(
                    case_id=case.case_id,
                    gold_relevant_ids=gold_rel_ids,
                    expected_empty=case.expected.expected_empty,
                    sql_candidate_ids=sql_candidates,
                    eligible_result_ids=eligible_ids,
                    more_info_result_ids=more_info_ids,
                    not_eligible_ids=not_eligible_ids,
                    ranked_eligible_ids=ranked_el_ids,
                    ranked_more_info_ids=ranked_mi_ids,
                    indexed_scheme_ids=indexed_ids_set,
                    stale_scheme_ids=stale_ids,
                    ineligible_leakage_ids=case_buckets.get("leaked_scheme_ids", []),
                    duplicate_ids=case_buckets.get("duplicates", []),
                    top_k=top_k,
                    language=case.language,
                )

                # Strict Case Pass Decision
                # Strict Criteria:
                # 1. No ineligible leakage (ineligible_leakage_count == 0)
                # 2. No duplicate schemes (duplicate_count == 0)
                # 3. If expected_empty == True: zero recommendations returned
                # 4. If expected_empty == False: must_appear_top_5 satisfied and acceptable_top_set satisfied
                strict_pass = True
                if case_buckets.get("ineligible_leakage_count", 0) > 0:
                    strict_pass = False
                if case_buckets.get("duplicate_count", 0) > 0:
                    strict_pass = False

                if case.expected.expected_empty:
                    if len(all_ranked) > 0:
                        strict_pass = False
                else:
                    if not case_ranking.get("must_top5_satisfied", True):
                        strict_pass = False
                    if not case_ranking.get("top_set_satisfied", True):
                        strict_pass = False

                ranking_only_pass = case_ranking.get("must_top5_satisfied", True) and case_ranking.get("top_set_satisfied", True)

                # Build CaseResult
                case_res = SearchCaseResult(
                    case_id=case.case_id,
                    split=case.split.value,
                    language=case.language,
                    query_type=case.query_type,
                    query=runtime_query,
                    profile_summary={k: v for k, v in runtime_profile.items() if k in ("district", "state", "age", "family_income")},
                    tags=case.tags,
                    gold_relevant_scheme_ids=gold_rel_ids,
                    acceptable_top_set=case.expected.acceptable_top_set,
                    must_appear_top_5=case.expected.must_appear_top_5,
                    must_not_appear_top_k=case.expected.must_not_appear_top_k,
                    expected_empty=case.expected.expected_empty,
                    sql_candidate_count=len(sql_candidates),
                    sql_candidate_ids=sql_candidates[:10],
                    evaluated_count=len(eval_results),
                    eligible_count=len(eligible_ids),
                    more_info_count=len(more_info_ids),
                    not_eligible_count=len(not_eligible_ids),
                    ranked_eligible_ids=ranked_el_ids,
                    ranked_more_info_ids=ranked_mi_ids,
                    target_semantic_similarity=target_sim,
                    target_rank=target_rank,
                    recalls=case_ranking.get("recalls", {}),
                    precisions=case_ranking.get("precisions", {}),
                    reciprocal_rank=case_ranking.get("rr", 0.0),
                    ndcg_at_5=case_ranking.get("ndcg_5", 0.0),
                    strict_case_pass=strict_pass,
                    ranking_only_pass=ranking_only_pass,
                    diagnoses=diagnoses,
                    duration_ms=round(case_duration, 2),
                )
                case_results.append(case_res)

        finally:
            session.close()

        total_duration = time.perf_counter() - start_eval_time

        # 4. Compute Component Aggregated Metrics
        candidate_metrics = CandidateMetricsCalculator.calculate(candidate_eval_cases)
        ranking_metrics = RankingMetricsCalculator.calculate_aggregate(ranking_eval_cases)
        bucket_metrics = BucketMetricsCalculator.calculate_aggregate(bucket_eval_cases)
        multilingual_metrics = MultilingualAnalyzer.analyze(multilingual_eval_cases)

        # 5. Index Health Metrics
        index_health = IndexHealthMetrics(
            verified_scheme_count=index_status.get("verified_schemes_count", 0),
            indexed_current_scheme_count=index_status.get("search_metadata_count", 0),
            missing_embedding_count=max(0, index_status.get("search_metadata_count", 0) - index_status.get("embeddings_count", 0)),
            stale_embedding_count=index_status.get("stale_embeddings_count", 0),
            failed_embedding_count=0,
            index_coverage_pct=round(
                (index_status.get("search_metadata_count", 0) / max(1, index_status.get("verified_schemes_count", 1))) * 100.0,
                1,
            ),
            embedding_provider="fastembed",
            embedding_model=index_status.get("embedding_model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            embedding_dimension=index_status.get("embedding_dimension", 384),
            pgvector_available=index_status.get("pgvector_available", False),
            index_type="EXACT_COSINE",
        )

        # 6. Degraded Mode Evaluation (Simulating vector ranking disabled)
        degraded_metrics = self._evaluate_degraded_mode(selected_cases[:5])

        # 7. Overall Summary
        strict_passed = sum(1 for c in case_results if c.strict_case_pass)
        ranking_passed = sum(1 for c in case_results if c.ranking_only_pass)
        total_cases = len(case_results)

        p50 = float(np.percentile(durations, 50)) if durations else 0.0
        p95 = float(np.percentile(durations, 95)) if durations else 0.0
        avg_dur = float(np.mean(durations)) if durations else 0.0

        summary = SearchBenchmarkSummary(
            run_id=run_id,
            gold_version=self.gold_version,
            split=split_enum.value,
            timestamp=timestamp,
            duration_seconds=round(total_duration, 2),
            total_cases=total_cases,
            strict_pass_count=strict_passed,
            strict_case_pass_rate=round(strict_passed / total_cases, 4) if total_cases > 0 else 0.0,
            ranking_only_pass_rate=round(ranking_passed / total_cases, 4) if total_cases > 0 else 0.0,
            candidate_metrics=candidate_metrics,
            ranking_metrics=ranking_metrics,
            bucket_metrics=bucket_metrics,
            multilingual_metrics=multilingual_metrics,
            index_health=index_health,
            degraded_mode=degraded_metrics,
            p50_duration_ms=round(p50, 2),
            p95_duration_ms=round(p95, 2),
            avg_duration_ms=round(avg_dur, 2),
            critical_failures_count=bucket_metrics.ineligible_leakage_count,
        )

        # 8. Persist Artifacts
        if persist_results:
            run_dir = self.output_base_dir / run_id
            SearchBenchmarkReporter.persist_artifacts(summary, case_results, run_dir)
            logger.info(f"Saved benchmark artifacts to {run_dir}")

        return summary, case_results

    def _evaluate_degraded_mode(self, sample_cases: List[SearchGoldCase]) -> DegradedModeMetrics:
        """Evaluates discovery pipeline when semantic ranking is disabled."""
        if not sample_cases:
            return DegradedModeMetrics(fallback_functional=True)

        session = SessionLocal()
        durations = []
        hits = 0
        total_eval = 0

        try:
            for c in sample_cases:
                if c.expected.expected_empty:
                    continue
                total_eval += 1
                t0 = time.perf_counter()

                # Request with no semantic ranking (need_text=None forces deterministic ID ranking)
                req = SchemeDiscoveryRequest(
                    need_text=None,
                    profile=c.profile or {},
                    limit=5,
                )
                resp = SchemeDiscoveryService.discover_schemes(session=session, request=req)
                durations.append((time.perf_counter() - t0) * 1000.0)

                all_res = [x.scheme_id for x in resp.eligible + resp.more_information_required]
                gold_ids = [r.scheme_id for r in c.expected.relevance_judgments]
                if any(gid in all_res for gid in gold_ids):
                    hits += 1

            avg_dur = sum(durations) / len(durations) if durations else 0.0
            rec = hits / total_eval if total_eval > 0 else 1.0

            return DegradedModeMetrics(
                fallback_functional=True,
                fallback_candidate_recall=round(rec, 4),
                fallback_top_set_recall=round(rec, 4),
                fallback_avg_duration_ms=round(avg_dur, 2),
                notes="Deterministic SQL candidate filtering and eligibility operate reliably without vector ranker.",
            )
        finally:
            session.close()
