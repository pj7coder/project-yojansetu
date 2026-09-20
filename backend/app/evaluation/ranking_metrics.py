"""
YojanSetu - Day 31: Ranking Quality & Semantic Retrieval Metrics Evaluator.

Evaluates Stage D & E (Semantic Vector Ranking & Output Ordering):
- Recall@1, Recall@3, Recall@5, Recall@10
- Precision@1, Precision@3, Precision@5, Precision@10
- MRR (Mean Reciprocal Rank)
- NDCG@K (Normalized Discounted Cumulative Gain with graded relevance)
- Top-Set Recall: Schemes in acceptable_top_set / must_appear_top_5 in top K
- Exact Name Hit Rate: Hit rate when query contains exact scheme name
- No-Result False Recommendation Rate: Measures zero-result safety
"""

import math
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class RankingMetrics(BaseModel):
    """Aggregated metrics for semantic ranking and top-K recommendation quality."""
    total_query_cases: int = 0
    total_relevant_queries: int = 0

    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0

    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0

    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0

    top_set_recall: float = 0.0
    exact_name_hit_rate: float = 0.0

    # Zero-result safety
    total_no_result_cases: int = 0
    no_result_false_recommendations: int = 0
    false_recommendation_rate_on_no_result_cases: float = 0.0


class RankingMetricsCalculator:
    """Computes standard Information Retrieval ranking metrics."""

    RELEVANCE_GAIN = {
        "HIGH": 2.0,
        "RELEVANT": 1.0,
        "NOT_RELEVANT": 0.0,
    }

    @classmethod
    def calculate_case_ranking(
        cls,
        ranked_scheme_ids: List[str],
        gold_relevant_scheme_ids: List[str],
        graded_judgments: Optional[Dict[str, str]] = None,
        acceptable_top_set: Optional[List[str]] = None,
        must_appear_top_5: Optional[List[str]] = None,
        expected_empty: bool = False,
    ) -> Dict[str, Any]:
        """Calculates single-case ranking metrics."""
        gold_rel_set = set(gold_relevant_scheme_ids)
        graded = graded_judgments or {}
        acc_top_set = set(acceptable_top_set or [])
        must_top5 = set(must_appear_top_5 or [])

        case_res: Dict[str, Any] = {
            "expected_empty": expected_empty,
            "has_relevant": len(gold_rel_set) > 0,
            "first_rank": None,
            "rr": 0.0,
            "recalls": {},
            "precisions": {},
            "top_set_satisfied": True,
            "must_top5_satisfied": True,
            "false_recommendation_on_empty": False,
        }

        if expected_empty:
            case_res["false_recommendation_on_empty"] = len(ranked_scheme_ids) > 0
            return case_res

        # Calculate Recall@K and Precision@K
        ks = [1, 3, 5, 10]
        for k in ks:
            top_k = ranked_scheme_ids[:k]
            hits = len(gold_rel_set.intersection(top_k))
            rec = hits / len(gold_rel_set) if gold_rel_set else 1.0
            prec = hits / k if k > 0 else 0.0
            case_res["recalls"][k] = round(rec, 4)
            case_res["precisions"][k] = round(prec, 4)

        # Reciprocal Rank (MRR)
        for idx, sid in enumerate(ranked_scheme_ids):
            if sid in gold_rel_set:
                case_res["first_rank"] = idx + 1
                case_res["rr"] = 1.0 / (idx + 1)
                break

        # NDCG@5 and NDCG@10
        case_res["dcg_5"] = cls._compute_dcg(ranked_scheme_ids[:5], graded)
        case_res["idcg_5"] = cls._compute_idcg(graded, 5)
        case_res["ndcg_5"] = (
            case_res["dcg_5"] / case_res["idcg_5"] if case_res["idcg_5"] > 0 else (1.0 if not gold_rel_set else 0.0)
        )

        case_res["dcg_10"] = cls._compute_dcg(ranked_scheme_ids[:10], graded)
        case_res["idcg_10"] = cls._compute_idcg(graded, 10)
        case_res["ndcg_10"] = (
            case_res["dcg_10"] / case_res["idcg_10"] if case_res["idcg_10"] > 0 else (1.0 if not gold_rel_set else 0.0)
        )

        # Acceptable Top Set & Must Appear Top 5 checks
        top_5_set = set(ranked_scheme_ids[:5])
        if must_top5:
            case_res["must_top5_satisfied"] = must_top5.issubset(top_5_set)
        if acc_top_set:
            case_res["top_set_satisfied"] = any(sid in top_5_set for sid in acc_top_set)

        return case_res

    @classmethod
    def calculate_aggregate(cls, case_evaluations: List[Dict[str, Any]]) -> RankingMetrics:
        """Aggregates ranking metrics across all evaluated discovery search cases."""
        metrics = RankingMetrics()
        metrics.total_query_cases = len(case_evaluations)
        if not case_evaluations:
            return metrics

        rec_1, rec_3, rec_5, rec_10 = [], [], [], []
        prec_1, prec_3, prec_5, prec_10 = [], [], [], []
        rr_list = []
        ndcg_5_list, ndcg_10_list = [], []

        top_set_passed = 0
        top_set_evaluated = 0

        exact_hits = 0
        exact_evaluated = 0

        no_res_cases = 0
        no_res_false_recs = 0

        for case in case_evaluations:
            expected_empty = case.get("expected_empty", False)
            if expected_empty:
                no_res_cases += 1
                if case.get("recommendation_count", 0) > 0:
                    no_res_false_recs += 1
                continue

            # Case has gold relevant expectations
            metrics.total_relevant_queries += 1

            cr = case.get("ranking_evaluation", {})
            recalls = cr.get("recalls", {})
            precisions = cr.get("precisions", {})

            rec_1.append(recalls.get(1, 0.0))
            rec_3.append(recalls.get(3, 0.0))
            rec_5.append(recalls.get(5, 0.0))
            rec_10.append(recalls.get(10, 0.0))

            prec_1.append(precisions.get(1, 0.0))
            prec_3.append(precisions.get(3, 0.0))
            prec_5.append(precisions.get(5, 0.0))
            prec_10.append(precisions.get(10, 0.0))

            rr_list.append(cr.get("rr", 0.0))
            ndcg_5_list.append(cr.get("ndcg_5", 0.0))
            ndcg_10_list.append(cr.get("ndcg_10", 0.0))

            # Top set recall
            if case.get("has_acceptable_top_set") or case.get("has_must_appear_top_5"):
                top_set_evaluated += 1
                if cr.get("top_set_satisfied", False) and cr.get("must_top5_satisfied", True):
                    top_set_passed += 1

            # Exact scheme name query check
            if case.get("query_type") == "EXACT_NAME" or "EXACT_NAME" in case.get("tags", []):
                exact_evaluated += 1
                if recalls.get(1, 0.0) >= 1.0 or recalls.get(3, 0.0) >= 1.0:
                    exact_hits += 1

        n_rel = max(1, metrics.total_relevant_queries)
        metrics.recall_at_1 = round(sum(rec_1) / n_rel, 4)
        metrics.recall_at_3 = round(sum(rec_3) / n_rel, 4)
        metrics.recall_at_5 = round(sum(rec_5) / n_rel, 4)
        metrics.recall_at_10 = round(sum(rec_10) / n_rel, 4)

        metrics.precision_at_1 = round(sum(prec_1) / n_rel, 4)
        metrics.precision_at_3 = round(sum(prec_3) / n_rel, 4)
        metrics.precision_at_5 = round(sum(prec_5) / n_rel, 4)
        metrics.precision_at_10 = round(sum(prec_10) / n_rel, 4)

        metrics.mrr = round(sum(rr_list) / n_rel, 4)
        metrics.ndcg_at_5 = round(sum(ndcg_5_list) / n_rel, 4)
        metrics.ndcg_at_10 = round(sum(ndcg_10_list) / n_rel, 4)

        metrics.top_set_recall = (
            round(top_set_passed / top_set_evaluated, 4) if top_set_evaluated > 0 else 1.0
        )
        metrics.exact_name_hit_rate = (
            round(exact_hits / exact_evaluated, 4) if exact_evaluated > 0 else 1.0
        )

        metrics.total_no_result_cases = no_res_cases
        metrics.no_result_false_recommendations = no_res_false_recs
        metrics.false_recommendation_rate_on_no_result_cases = (
            round(no_res_false_recs / no_res_cases, 4) if no_res_cases > 0 else 0.0
        )

        return metrics

    @classmethod
    def _compute_dcg(cls, scheme_ids: List[str], graded_judgments: Dict[str, str]) -> float:
        dcg = 0.0
        for i, sid in enumerate(scheme_ids):
            grade = graded_judgments.get(sid, "NOT_RELEVANT")
            gain = cls.RELEVANCE_GAIN.get(grade, 0.0)
            dcg += gain / math.log2(i + 2)
        return dcg

    @classmethod
    def _compute_idcg(cls, graded_judgments: Dict[str, str], k: int) -> float:
        gains = sorted(
            [cls.RELEVANCE_GAIN.get(g, 0.0) for g in graded_judgments.values()],
            reverse=True,
        )[:k]
        idcg = 0.0
        for i, gain in enumerate(gains):
            idcg += gain / math.log2(i + 2)
        return idcg
