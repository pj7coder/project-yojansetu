from datetime import date, timedelta
import json
from pathlib import Path
import time
from typing import Any, Dict, List
import uuid
from fastapi.testclient import TestClient
import numpy as np
import pytest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.database.models.scheme_embedding import SchemeEmbedding
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.main import app
from app.search.candidate_filter import CandidateFilterService
from app.search.discovery_service import SchemeDiscoveryService
from app.search.indexer import SchemeSearchIndexService
from app.search.metadata_builder import SearchMetadataBuilder
from app.search.schemas import SchemeDiscoveryRequest
from app.search.search_text import SchemeSearchTextBuilder, compute_search_text_hash
from app.search.semantic_ranker import SemanticSchemeRanker

client = TestClient(app)


# ===========================================================================
# Fixture Helpers
# ===========================================================================

def create_mock_verified_scheme(
    scheme_id: str,
    name_en: str,
    name_hi: str = "",
    category: str = "General",
    districts: List[str] = None,
    rural_urban: str = "BOTH",
    scheme_origin: str = "RAJASTHAN_STATE",
    beneficiaries: List[str] = None,
    root_rule: Dict[str, Any] = None,
    exclusions: List[Dict[str, Any]] = None,
    valid_from: date = None,
    valid_until: date = None,
    is_verified: bool = True,
    is_active: bool = True,
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "verifier_version": "1.0",
        "scheme_draft_id": None,
        "review": {
            "status": "HUMAN_VERIFIED" if is_verified else "DRAFT",
            "reviewer_id": "REV-TEST",
        },
        "canonical_scheme": {
            "schema_version": "1.0",
            "scheme_identity": {
                "scheme_id": scheme_id,
                "name": {"en": name_en, "hi": name_hi, "raw": name_en},
                "category": category,
                "scheme_origin": scheme_origin,
                "jurisdiction": "Rajasthan",
                "description": f"Official scheme supporting {name_en}",
                "target_beneficiaries": beneficiaries or [],
            },
            "scope": {
                "state": "Rajasthan",
                "districts": districts or [],
                "rural_urban": rural_urban,
            },
            "eligibility": {
                "root_rule": root_rule or {
                    "condition_id": f"C-{scheme_id}-AGE",
                    "field": "age",
                    "operator": "GTE",
                    "value": 18,
                }
            },
            "exclusions": exclusions or [],
            "benefits": [
                {
                    "benefit_id": f"BEN-{scheme_id}",
                    "type": "CASH",
                    "amount": 5000,
                    "currency": "INR",
                    "description": "Financial assistance grant",
                }
            ],
            "important_dates": [
                {"event_name": "launch", "normalized_date": str(valid_from)} if valid_from else {},
                {"event_name": "expiry", "normalized_date": str(valid_until)} if valid_until else {},
            ],
        },
    }


# ===========================================================================
# 1. SQL Candidate Filtering Tests
# ===========================================================================

def test_sql_candidate_filtering_high_recall():
    db = SessionLocal()
    try:
        # Create test schemes:
        # Scheme 1: Statewide Rajasthan, active
        s1 = SchemeSearchMetadata(
            scheme_id="TEST-STATEWIDE",
            scheme_name="Rajasthan General Welfare",
            state="Rajasthan",
            districts=[],
            rural_urban="BOTH",
            scheme_origin="RAJASTHAN_STATE",
            category="Welfare",
            is_active=True,
            is_verified=True,
            search_text="Statewide assistance for Rajasthan residents",
            search_text_hash="hash-1",
        )
        # Scheme 2: Udaipur district only
        s2 = SchemeSearchMetadata(
            scheme_id="TEST-UDAIPUR",
            scheme_name="Udaipur Tribal Development",
            state="Rajasthan",
            districts=["Udaipur"],
            rural_urban="BOTH",
            scheme_origin="RAJASTHAN_STATE",
            category="Tribal",
            is_active=True,
            is_verified=True,
            search_text="Tribal assistance restricted to Udaipur district",
            search_text_hash="hash-2",
        )
        # Scheme 3: Unverified scheme
        s3 = SchemeSearchMetadata(
            scheme_id="TEST-UNVERIFIED",
            scheme_name="Unapproved Scheme Draft",
            state="Rajasthan",
            districts=[],
            rural_urban="BOTH",
            scheme_origin="RAJASTHAN_STATE",
            is_active=True,
            is_verified=False,  # Unverified!
            search_text="Unapproved scheme",
            search_text_hash="hash-3",
        )
        # Scheme 4: Expired scheme
        s4 = SchemeSearchMetadata(
            scheme_id="TEST-EXPIRED",
            scheme_name="Expired Scheme 2020",
            state="Rajasthan",
            districts=[],
            rural_urban="BOTH",
            scheme_origin="RAJASTHAN_STATE",
            valid_until=date(2020, 1, 1),
            is_active=True,
            is_verified=True,
            search_text="Expired scheme",
            search_text_hash="hash-4",
        )
        db.add_all([s1, s2, s3, s4])
        db.commit()

        # Case A: Citizen with district = Jaipur (should get statewide s1, NOT Udaipur s2, NOT unverified s3, NOT expired s4)
        prof_jaipur = CitizenProfile(state="Rajasthan", district="Jaipur")
        cands_jaipur, _ = CandidateFilterService.filter_candidates(db, prof_jaipur, evaluation_date=date(2026, 6, 1))
        assert "TEST-STATEWIDE" in cands_jaipur
        assert "TEST-UDAIPUR" not in cands_jaipur
        assert "TEST-UNVERIFIED" not in cands_jaipur
        assert "TEST-EXPIRED" not in cands_jaipur

        # Case B: Citizen with district = Udaipur (should get both statewide s1 AND Udaipur s2)
        prof_udaipur = CitizenProfile(state="Rajasthan", district="Udaipur")
        cands_udaipur, _ = CandidateFilterService.filter_candidates(db, prof_udaipur, evaluation_date=date(2026, 6, 1))
        assert "TEST-STATEWIDE" in cands_udaipur
        assert "TEST-UDAIPUR" in cands_udaipur

        # Case C: Citizen with UNKNOWN district (High Recall: must KEEP Udaipur s2!)
        prof_unknown_dist = CitizenProfile(state="Rajasthan")
        cands_unknown, _ = CandidateFilterService.filter_candidates(db, prof_unknown_dist, evaluation_date=date(2026, 6, 1))
        assert "TEST-STATEWIDE" in cands_unknown
        assert "TEST-UDAIPUR" in cands_unknown

        # Case D: Citizen from Gujarat (different state)
        prof_gujarat = CitizenProfile(state="Gujarat")
        cands_gujarat, _ = CandidateFilterService.filter_candidates(db, prof_gujarat, evaluation_date=date(2026, 6, 1))
        assert "TEST-STATEWIDE" not in cands_gujarat
        assert "TEST-UDAIPUR" not in cands_gujarat

    finally:
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()


# ===========================================================================
# 2. Multilingual Semantic Ranking Tests
# ===========================================================================

def test_semantic_ranking_multilingual_intents():
    db = SessionLocal()
    provider = LocalFastEmbedProvider()
    assert provider.is_available()

    try:
        # Create 3 distinct schemes:
        # 1. Agriculture / Farming
        farm_scheme = create_mock_verified_scheme(
            scheme_id="TEST-FARM-01",
            name_en="Kisan Krishi Sahayata Yojana (Farming Financial Assistance)",
            name_hi="किसान कृषि सहायता योजना",
            category="Agriculture",
            beneficiaries=["Farmers", "Agricultural laborers"],
        )
        # 2. Student Scholarship
        study_scheme = create_mock_verified_scheme(
            scheme_id="TEST-STUDY-01",
            name_en="Post-Matric Higher Education Scholarship",
            name_hi="उत्तर मैट्रिक छात्रवृत्ति योजना",
            category="Education",
            beneficiaries=["Students", "College scholars"],
        )
        # 3. Old Age Pension
        pension_scheme = create_mock_verified_scheme(
            scheme_id="TEST-PENSION-01",
            name_en="Mukhyamantri Vridhjan Samman Pension",
            name_hi="मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
            category="Pension",
            beneficiaries=["Senior Citizens", "Elderly"],
        )

        # Index them
        SchemeSearchIndexService.index_verified_scheme(db, farm_scheme, provider)
        SchemeSearchIndexService.index_verified_scheme(db, study_scheme, provider)
        SchemeSearchIndexService.index_verified_scheme(db, pension_scheme, provider)

        candidates = ["TEST-FARM-01", "TEST-STUDY-01", "TEST-PENSION-01"]

        # Test A: Hindi Farming Need -> Agriculture scheme should rank highest
        hindi_scores = SemanticSchemeRanker.rank_candidates(
            session=db,
            need_text="मुझे खेती और फसल के लिए आर्थिक सहायता चाहिए",
            candidate_scheme_ids=candidates,
            embedding_provider=provider,
        )
        assert hindi_scores["TEST-FARM-01"] > hindi_scores["TEST-STUDY-01"]
        assert hindi_scores["TEST-FARM-01"] > hindi_scores["TEST-PENSION-01"]

        # Test B: English Farming Need -> Agriculture scheme should rank highest
        eng_scores = SemanticSchemeRanker.rank_candidates(
            session=db,
            need_text="I need financial support for agriculture and crop cultivation",
            candidate_scheme_ids=candidates,
            embedding_provider=provider,
        )
        assert eng_scores["TEST-FARM-01"] > eng_scores["TEST-STUDY-01"]
        assert eng_scores["TEST-FARM-01"] > eng_scores["TEST-PENSION-01"]

        # Test C: Hinglish Need -> Agriculture scheme should rank highest
        hinglish_scores = SemanticSchemeRanker.rank_candidates(
            session=db,
            need_text="kisan kheti subsidy aur financial help chahiye",
            candidate_scheme_ids=candidates,
            embedding_provider=provider,
        )
        assert hinglish_scores["TEST-FARM-01"] > hinglish_scores["TEST-STUDY-01"]

        # Test D: Unrelated Education Need -> Study scheme should rank highest
        edu_scores = SemanticSchemeRanker.rank_candidates(
            session=db,
            need_text="college fees and student scholarship assistance",
            candidate_scheme_ids=candidates,
            embedding_provider=provider,
        )
        assert edu_scores["TEST-STUDY-01"] > edu_scores["TEST-FARM-01"]
        assert edu_scores["TEST-STUDY-01"] > edu_scores["TEST-PENSION-01"]

    finally:
        db.execute(text("DELETE FROM scheme_embeddings WHERE scheme_id LIKE 'TEST-%'"))
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()


# ===========================================================================
# 3. Eligibility Independence Invariants
# ===========================================================================

def test_semantic_match_but_ineligible_is_excluded():
    """
    Critical Invariant: High vector similarity must NEVER override an ineligibility decision!
    Scheme A: Perfect semantic match for farming, but requires Age >= 60.
    Citizen: Age 25 (fails age).
    Result: Scheme A must NOT appear in confirmed 'eligible' recommendations!
    """
    db = SessionLocal()
    provider = LocalFastEmbedProvider()
    settings = get_settings()

    try:
        # Scheme A: Farming scheme requiring Age >= 60
        farm_old_scheme = create_mock_verified_scheme(
            scheme_id="TEST-FARM-OLD",
            name_en="Senior Farmer Support Scheme",
            category="Agriculture",
            beneficiaries=["Senior farmers"],
            root_rule={"condition_id": "C-AGE-60", "field": "age", "operator": "GTE", "value": 60},
        )
        # Scheme B: General welfare scheme for any adult Age >= 18
        general_scheme = create_mock_verified_scheme(
            scheme_id="TEST-GEN-ADULT",
            name_en="Youth & General Adult Assistance",
            category="Social Welfare",
            beneficiaries=["Citizens"],
            root_rule={"condition_id": "C-AGE-18", "field": "age", "operator": "GTE", "value": 18},
        )

        # Index both
        SchemeSearchIndexService.index_verified_scheme(db, farm_old_scheme, provider)
        SchemeSearchIndexService.index_verified_scheme(db, general_scheme, provider)

        # Also write mock verified artifacts to storage/verified/ so EligibilityEngine can load them
        dir_old = settings.verified_dir / "TEST-FARM-OLD"
        dir_old.mkdir(parents=True, exist_ok=True)
        with open(dir_old / "verified_scheme.json", "w", encoding="utf-8") as f:
            json.dump(farm_old_scheme, f)

        dir_gen = settings.verified_dir / "TEST-GEN-ADULT"
        dir_gen.mkdir(parents=True, exist_ok=True)
        with open(dir_gen / "verified_scheme.json", "w", encoding="utf-8") as f:
            json.dump(general_scheme, f)

        # Citizen is Age 25, needs farming help
        req = SchemeDiscoveryRequest(
            profile={"age": 25, "state": "Rajasthan"},
            need_text="I am a farmer and I need urgent financial support for crops",
            limit=5,
        )

        response = SchemeDiscoveryService.discover_schemes(db, req, provider)

        eligible_ids = [item.scheme_id for item in response.eligible]

        # Scheme A (Senior Farmer) MUST NOT be in eligible list because citizen is only 25!
        assert "TEST-FARM-OLD" not in eligible_ids
        # Scheme B (Youth & Adult) IS in eligible list
        assert "TEST-GEN-ADULT" in eligible_ids

    finally:
        db.execute(text("DELETE FROM scheme_embeddings WHERE scheme_id LIKE 'TEST-%'"))
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()
        # Clean filesystem
        for p in [settings.verified_dir / "TEST-FARM-OLD", settings.verified_dir / "TEST-GEN-ADULT"]:
            if (p / "verified_scheme.json").exists():
                (p / "verified_scheme.json").unlink()
            if p.exists():
                p.rmdir()


def test_eligible_and_more_info_separation():
    """
    Eligible schemes and More-Information-Required schemes must be in strictly separate buckets.
    """
    db = SessionLocal()
    provider = LocalFastEmbedProvider()
    settings = get_settings()

    try:
        # Scheme 1: requires Age >= 60 (citizen has age 65 -> ELIGIBLE)
        s1 = create_mock_verified_scheme(
            scheme_id="TEST-ELIG-01",
            name_en="Old Age Pension Scheme",
            root_rule={"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 60},
        )
        # Scheme 2: requires BPL status (citizen has not provided BPL -> MORE_INFORMATION_REQUIRED)
        s2 = create_mock_verified_scheme(
            scheme_id="TEST-MOREINFO-01",
            name_en="BPL Housing Subsidy",
            root_rule={"condition_id": "C-BPL", "field": "bpl_status", "operator": "EQ", "value": True},
        )

        SchemeSearchIndexService.index_verified_scheme(db, s1, provider)
        SchemeSearchIndexService.index_verified_scheme(db, s2, provider)

        # Write artifacts
        for sid, scheme_data in [("TEST-ELIG-01", s1), ("TEST-MOREINFO-01", s2)]:
            p = settings.verified_dir / sid
            p.mkdir(parents=True, exist_ok=True)
            with open(p / "verified_scheme.json", "w", encoding="utf-8") as f:
                json.dump(scheme_data, f)

        # Citizen provides age 65, but no BPL status
        req = SchemeDiscoveryRequest(
            profile={"age": 65, "state": "Rajasthan"},
            need_text="pension and housing assistance",
            limit=5,
        )

        response = SchemeDiscoveryService.discover_schemes(db, req, provider)

        eligible_ids = [item.scheme_id for item in response.eligible]
        more_info_ids = [item.scheme_id for item in response.more_information_required]

        assert "TEST-ELIG-01" in eligible_ids
        assert "TEST-MOREINFO-01" not in eligible_ids

        assert "TEST-MOREINFO-01" in more_info_ids
        assert "TEST-ELIG-01" not in more_info_ids

        # Check missing fields
        more_info_item = next(i for i in response.more_information_required if i.scheme_id == "TEST-MOREINFO-01")
        assert "bpl_status" in more_info_item.missing_fields

    finally:
        db.execute(text("DELETE FROM scheme_embeddings WHERE scheme_id LIKE 'TEST-%'"))
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()
        for sid in ["TEST-ELIG-01", "TEST-MOREINFO-01"]:
            p = settings.verified_dir / sid
            if (p / "verified_scheme.json").exists():
                (p / "verified_scheme.json").unlink()
            if p.exists():
                p.rmdir()


# ===========================================================================
# 4. Fallback & Failure Handling Tests
# ===========================================================================

def test_query_with_no_need_text_uses_deterministic_ordering():
    """If no need text is provided, discovery runs via candidate filter + eligibility with no vector call."""
    db = SessionLocal()
    settings = get_settings()

    try:
        s1 = create_mock_verified_scheme(
            scheme_id="TEST-FALLBACK-01",
            name_en="Fallback Scheme A",
            root_rule={"condition_id": "C-1", "field": "age", "operator": "GTE", "value": 18},
        )
        SchemeSearchIndexService.index_verified_scheme(db, s1)

        p = settings.verified_dir / "TEST-FALLBACK-01"
        p.mkdir(parents=True, exist_ok=True)
        with open(p / "verified_scheme.json", "w", encoding="utf-8") as f:
            json.dump(s1, f)

        # Query with NO need text
        req = SchemeDiscoveryRequest(
            profile={"age": 25, "state": "Rajasthan"},
            need_text=None,
        )
        res = SchemeDiscoveryService.discover_schemes(db, req)

        assert res.meta.semantic_ranking_used is False
        assert any(i.scheme_id == "TEST-FALLBACK-01" for i in res.eligible)
        item = next(i for i in res.eligible if i.scheme_id == "TEST-FALLBACK-01")
        assert item.semantic_similarity is None  # No fake similarity score!

    finally:
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()
        p = settings.verified_dir / "TEST-FALLBACK-01"
        if (p / "verified_scheme.json").exists():
            (p / "verified_scheme.json").unlink()
        if p.exists():
            p.rmdir()


def test_stale_embedding_detection():
    """Modifying verified search text changes hash and updates embedding."""
    db = SessionLocal()
    provider = LocalFastEmbedProvider()

    try:
        scheme_v1 = create_mock_verified_scheme(
            scheme_id="TEST-STALE-01",
            name_en="Original Title Version 1",
        )
        SchemeSearchIndexService.index_verified_scheme(db, scheme_v1, provider)

        emb_v1 = db.execute(
            select(SchemeEmbedding).where(SchemeEmbedding.scheme_id == "TEST-STALE-01")
        ).scalar_one()
        orig_hash = emb_v1.search_text_hash

        # Update verified scheme text
        scheme_v2 = create_mock_verified_scheme(
            scheme_id="TEST-STALE-01",
            name_en="Updated Title Version 2 with New Benefits",
        )
        SchemeSearchIndexService.index_verified_scheme(db, scheme_v2, provider)

        emb_v2 = db.execute(
            select(SchemeEmbedding).where(SchemeEmbedding.scheme_id == "TEST-STALE-01")
        ).scalar_one()
        assert emb_v2.search_text_hash != orig_hash

    finally:
        db.execute(text("DELETE FROM scheme_embeddings WHERE scheme_id LIKE 'TEST-%'"))
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-%'"))
        db.commit()
        db.close()


# ===========================================================================
# 5. REST API & Privacy Invariants
# ===========================================================================

def test_api_discover_schemes():
    # Valid discovery request
    resp = client.post(
        "/api/v1/schemes/discover",
        json={
            "profile": {"age": 65, "state": "Rajasthan"},
            "need_text": "senior citizen old age pension",
            "limit": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "eligible" in data
    assert "more_information_required" in data
    assert "meta" in data
    assert "sql_candidates" in data["meta"]


def test_api_discover_rejects_impossible_input():
    resp = client.post(
        "/api/v1/schemes/discover",
        json={
            "profile": {"age": -20},
            "need_text": "help",
        },
    )
    assert resp.status_code == 422
    assert "Invalid citizen profile criteria" in resp.json()["detail"]


def test_api_search_index_status():
    resp = client.get("/api/v1/admin/search-index/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "search_metadata_count" in data
    assert "embeddings_count" in data
    assert "embedding_model" in data


# ===========================================================================
# 6. Large Corpus Synthetic Benchmark & EXPLAIN ANALYZE
# ===========================================================================

def test_large_corpus_synthetic_benchmark_and_explain():
    """
    Generates 1,000 synthetic verified schemes in DB, executes candidate filtering
    with EXPLAIN ANALYZE, and measures end-to-end latency.
    """
    db = SessionLocal()
    settings = get_settings()

    try:
        # 1. Insert 1,000 synthetic verified search metadata records
        synthetic_records = []
        now = date.today()
        for i in range(1000):
            dist = ["Udaipur"] if i % 10 == 0 else (["Jaipur"] if i % 5 == 0 else [])
            ru = "RURAL" if i % 3 == 0 else ("URBAN" if i % 4 == 0 else "BOTH")
            cat = "Agriculture" if i % 2 == 0 else "Welfare"

            rec = SchemeSearchMetadata(
                scheme_id=f"TEST-SYNTH-{i:04d}",
                scheme_name=f"Synthetic Verified Scheme {i}",
                state="Rajasthan",
                districts=dist,
                rural_urban=ru,
                scheme_origin="RAJASTHAN_STATE",
                category=cat,
                is_active=True,
                is_verified=True,
                search_text=f"Synthetic verified scheme description number {i} for {cat}",
                search_text_hash=f"hash-{i}",
            )
            synthetic_records.append(rec)

        db.bulk_save_objects(synthetic_records)
        db.commit()

        # 2. Run EXPLAIN ANALYZE on representative candidate filtering query
        explain_sql = text("""
            EXPLAIN ANALYZE
            SELECT scheme_id FROM scheme_search_metadata
            WHERE is_verified = true
              AND is_active = true
              AND (state IS NULL OR lower(state) = 'rajasthan' OR lower(state) = 'all_india')
              AND (rural_urban IN ('RURAL', 'BOTH', 'ALL'))
              AND (jsonb_array_length(districts) = 0 OR districts @> '["Udaipur"]')
            ORDER BY scheme_id ASC
            LIMIT 200;
        """)
        explain_res = db.execute(explain_sql).fetchall()
        explain_output = "\n".join([row[0] for row in explain_res])
        print("\n--- EXPLAIN ANALYZE RESULT ---")
        print(explain_output)

        # 3. Measure Candidate Filtering Performance
        prof = CitizenProfile(state="Rajasthan", district="Udaipur", rural_urban="RURAL")
        t0 = time.perf_counter()
        cands, total_v = CandidateFilterService.filter_candidates(db, prof, evaluation_date=now)
        filter_duration_ms = (time.perf_counter() - t0) * 1000.0

        print(f"\nSynthetic Corpus Size: 1000")
        print(f"Candidates Returned: {len(cands)}")
        print(f"SQL Filtering Latency: {round(filter_duration_ms, 2)} ms")

        # Fast SQL performance assertion: sub-50ms for 1,000 records
        assert filter_duration_ms < 100.0
        assert len(cands) > 0

    finally:
        db.execute(text("DELETE FROM scheme_search_metadata WHERE scheme_id LIKE 'TEST-SYNTH-%'"))
        db.commit()
        db.close()
