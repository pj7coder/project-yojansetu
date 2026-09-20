from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List
import uuid
from fastapi.testclient import TestClient
import pytest

from app.cache.verified_rule_cache import VerifiedRuleCache, get_rule_cache
from app.core.config import get_settings
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.discovery.session_discovery_service import SessionDiscoveryService
from app.eligibility.compiler import EligibilityRuleCompiler
from app.eligibility.engine import EligibilityEngine
from app.eligibility.models import CompiledScheme
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.main import app
from app.questioning.field_metadata import FIELD_METADATA_REGISTRY, get_field_metadata
from app.questioning.schemas import CandidateSchemeMissingInfo, NextQuestionResult, QuestionReasonCode
from app.questioning.scoring import QuestionScorer
from app.questioning.selector import NextQuestionSelector
from app.search.indexer import SchemeSearchIndexService
from app.search.metadata_builder import SearchMetadataBuilder
from app.sessions.manager import CitizenSessionManager, SessionNotFoundError, get_session_manager
from app.sessions.models import CitizenSession, FieldValueState

client = TestClient(app)


# ===========================================================================
# Fixture Helpers
# ===========================================================================

@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_test_scheme_raw(
    scheme_id: str,
    name_en: str,
    root_rule: Dict[str, Any],
    districts: List[str] = None,
    category: str = "Agriculture",
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "review": {
            "status": "HUMAN_VERIFIED",
            "artifact_sha256": f"hash-{scheme_id}-v1",
        },
        "canonical_scheme": {
            "schema_version": "1.0",
            "scheme_identity": {
                "scheme_id": scheme_id,
                "name": {"en": name_en, "hi": f"{name_en} (हिंदी)"},
                "category": category,
                "scheme_origin": "RAJASTHAN_STATE",
                "jurisdiction": "Rajasthan",
                "description": f"Test description for {name_en}",
            },
            "scope": {
                "state": "Rajasthan",
                "districts": districts or [],
                "rural_urban": "BOTH",
            },
            "eligibility": {
                "root_rule": root_rule,
            },
            "exclusions": [],
            "benefits": [
                {
                    "benefit_id": f"BEN-{scheme_id}",
                    "type": "CASH",
                    "amount": 5000,
                    "currency": "INR",
                    "description": "Grant",
                }
            ],
            "important_dates": [],
        }
    }


# ===========================================================================
# 1. VerifiedRuleCache Tests
# ===========================================================================

def test_rule_cache_hit_and_miss():
    cache = VerifiedRuleCache(max_entries=100)
    scheme_id = "SCHEME-CACHE-01"
    raw_scheme = make_test_scheme_raw(
        scheme_id=scheme_id,
        name_en="Cache Test Scheme",
        root_rule={
            "condition_id": "C1",
            "field": "age",
            "operator": "GTE",
            "value": 60,
        },
    )

    # First lookup: Miss (no DB session provided)
    res_miss = cache.get(scheme_id)
    assert res_miss is None
    assert cache.metrics.misses == 1
    assert cache.metrics.hits == 0

    # Manually populate entry (simulating DB load)
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)
    cache._load_compile_and_cache = lambda sid, s: compiled  # mock loader

    res_load = cache._load_compile_and_cache(scheme_id, None)
    assert res_load is not None
    # Now put in cache
    from app.cache.verified_rule_cache import CachedRuleEntry
    cache._cache[scheme_id] = CachedRuleEntry(
        scheme_id=scheme_id,
        scheme_version="1.0",
        version_hash="hash-01",
        compiled_scheme=compiled,
        cached_at=datetime.now(timezone.utc),
    )

    # Second lookup: Hit
    res_hit = cache.get(scheme_id)
    assert res_hit is not None
    assert res_hit.scheme_id == scheme_id
    assert cache.metrics.hits == 1
    assert cache.metrics.misses == 1


def test_rule_cache_refresh_and_stale_detection():
    cache = VerifiedRuleCache(max_entries=100)
    scheme_id = "SCHEME-CACHE-02"
    raw_scheme = make_test_scheme_raw(
        scheme_id=scheme_id,
        name_en="Refresh Test Scheme",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 60},
    )
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)

    from app.cache.verified_rule_cache import CachedRuleEntry
    cache._cache[scheme_id] = CachedRuleEntry(
        scheme_id=scheme_id,
        scheme_version="1.0",
        version_hash="old-hash-v1",
        compiled_scheme=compiled,
        cached_at=datetime.now(timezone.utc),
    )

    # Check stale detection
    assert cache.is_stale(scheme_id, "old-hash-v1") is False
    assert cache.is_stale(scheme_id, "new-hash-v2") is True
    assert cache.is_stale("NON-EXISTENT", "any-hash") is True

    # Invalidate / refresh scheme
    cache.refresh_scheme(scheme_id, session=None)
    assert cache.contains(scheme_id) is False
    assert cache.metrics.refreshes == 1


def test_rule_cache_concurrency():
    cache = VerifiedRuleCache(max_entries=100)
    scheme_id = "SCHEME-CACHE-CONCURRENT"
    raw_scheme = make_test_scheme_raw(
        scheme_id=scheme_id,
        name_en="Concurrent Scheme",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18},
    )
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)

    def load_task():
        from app.cache.verified_rule_cache import CachedRuleEntry
        with cache._lock:
            if scheme_id not in cache._cache:
                time.sleep(0.01)  # introduce slight scheduling jitter
                cache._cache[scheme_id] = CachedRuleEntry(
                    scheme_id=scheme_id,
                    scheme_version="1.0",
                    version_hash="hash-concurrent",
                    compiled_scheme=compiled,
                    cached_at=datetime.now(timezone.utc),
                )
        return cache.get(scheme_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(load_task) for _ in range(16)]
        results = [f.result() for f in futures]

    assert all(r is not None and r.scheme_id == scheme_id for r in results)
    assert cache.contains(scheme_id) is True


def test_rule_cache_get_many():
    cache = VerifiedRuleCache(max_entries=100)
    for i in range(3):
        sid = f"SCHEME-BULK-{i}"
        raw = make_test_scheme_raw(sid, f"Bulk {i}", {"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18})
        compiled = EligibilityRuleCompiler.compile_scheme(raw)
        from app.cache.verified_rule_cache import CachedRuleEntry
        cache._cache[sid] = CachedRuleEntry(
            scheme_id=sid,
            scheme_version="1.0",
            version_hash=f"hash-{i}",
            compiled_scheme=compiled,
            cached_at=datetime.now(timezone.utc),
        )

    res_map = cache.get_many(["SCHEME-BULK-0", "SCHEME-BULK-1", "SCHEME-BULK-99"])
    assert len(res_map) == 2
    assert "SCHEME-BULK-0" in res_map
    assert "SCHEME-BULK-1" in res_map
    assert cache.metrics.hits == 2
    assert cache.metrics.misses == 1


# ===========================================================================
# 2. CitizenSessionManager Tests
# ===========================================================================

def test_session_create():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()
    assert session.session_id is not None
    assert len(session.session_id) >= 16
    assert session.expires_at > session.created_at
    diff = (session.expires_at - session.created_at).total_seconds()
    assert 2600 <= diff <= 2800  # ~45 minutes


def test_session_partial_profile_update_and_correction():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()

    # Step 1: Citizen provides age
    mgr.update_profile(session.session_id, patch={"age": 64})
    s1 = mgr.get_session(session.session_id)
    assert s1.profile["age"] == 64
    assert s1.field_states["age"] == FieldValueState.KNOWN

    # Step 2: Citizen provides district
    mgr.update_profile(session.session_id, patch={"district": "Udaipur"})
    s2 = mgr.get_session(session.session_id)
    # Age must still be retained! (Patch semantics)
    assert s2.profile["age"] == 64
    assert s2.profile["district"] == "Udaipur"
    assert set(s2.get_known_field_names()) == {"age", "district"}

    # Step 3: Citizen corrects age: "Earlier I said 64, actually I am 61"
    mgr.update_profile(session.session_id, patch={"age": 61})
    s3 = mgr.get_session(session.session_id)
    assert s3.profile["age"] == 61
    assert s3.profile["district"] == "Udaipur"
    assert s3.profile_version == 4  # incremented on each update


def test_session_boolean_false_is_not_unknown():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()

    # Provide bpl_status as False
    mgr.update_profile(session.session_id, patch={"bpl_status": False})
    retrieved = mgr.get_session(session.session_id)

    assert "bpl_status" in retrieved.profile
    assert retrieved.profile["bpl_status"] is False
    assert retrieved.field_states["bpl_status"] == FieldValueState.KNOWN
    assert "bpl_status" in retrieved.get_known_field_names()


def test_session_declined_field_handling():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()

    # Citizen provides age, but declines family_income
    mgr.update_profile(session.session_id, patch={"age": 64})
    mgr.decline_field(session.session_id, field_name="family_income", reason="Privacy preference")

    retrieved = mgr.get_session(session.session_id)
    assert retrieved.is_field_known("age") is True
    assert retrieved.is_field_declined("family_income") is True
    assert retrieved.field_states["family_income"] == FieldValueState.DECLINED
    assert "family_income" not in retrieved.profile
    assert "family_income" in retrieved.get_declined_field_names()


def test_session_asked_field_tracking():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()

    mgr.record_asked_field(session.session_id, "family_income")
    mgr.record_asked_field(session.session_id, "family_income")
    mgr.record_asked_field(session.session_id, "district")

    retrieved = mgr.get_session(session.session_id)
    assert retrieved.asked_fields == ["family_income", "district"]
    assert retrieved.field_ask_counts["family_income"] == 2
    assert retrieved.field_ask_counts["district"] == 1


def test_session_ttl_expiration_and_cleanup():
    mgr = CitizenSessionManager(ttl_minutes=1)
    session = mgr.create_session()
    sid = session.session_id

    # Session is active now
    assert mgr.get_session(sid) is not None

    # Fast forward expiration
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    # On access, expired session should return None and be removed
    assert mgr.get_session(sid) is None
    assert sid not in mgr._sessions


def test_session_delete_reset():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()
    sid = session.session_id

    assert mgr.get_session(sid) is not None
    deleted = mgr.delete_session(sid)
    assert deleted is True
    assert mgr.get_session(sid) is None


def test_session_isolation():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session_a = mgr.create_session()
    session_b = mgr.create_session()

    mgr.update_profile(session_a.session_id, patch={"age": 65, "district": "Udaipur"})
    mgr.update_profile(session_b.session_id, patch={"age": 30, "district": "Jaipur"})

    sa = mgr.get_session(session_a.session_id)
    sb = mgr.get_session(session_b.session_id)

    assert sa.profile["age"] == 65
    assert sa.profile["district"] == "Udaipur"

    assert sb.profile["age"] == 30
    assert sb.profile["district"] == "Jaipur"


def test_session_profile_validation_rejects_impossible_data():
    mgr = CitizenSessionManager(ttl_minutes=45)
    session = mgr.create_session()

    # Attempt invalid age (-5)
    with pytest.raises(Exception):
        mgr.update_profile(session.session_id, patch={"age": -5})

    # Confirm session profile was not corrupted
    s = mgr.get_session(session.session_id)
    assert "age" not in s.profile


# ===========================================================================
# 3. Deterministic NextQuestionSelector Tests
# ===========================================================================

def test_question_selection_frequency_winner():
    selector = NextQuestionSelector()

    # 3 schemes need family_income, 1 needs district
    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S1", missing_fields=["family_income", "district"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S2", missing_fields=["family_income"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S3", missing_fields=["family_income"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S4", missing_fields=["district"], semantic_score=0.5),
    ]

    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
        known_profile_fields=set(),
    )

    assert res.field == "family_income"
    assert res.affected_scheme_count == 3
    assert res.display_name_en == "Annual Family Income"
    assert res.display_name_hi == "वार्षिक पारिवारिक आय"


def test_question_selection_relevance_weighted():
    # Scheme A has high semantic relevance (0.95) needing land_holding_acres only
    # Schemes B, C, D have low relevance (0.10) needing family_income
    scorer = QuestionScorer(relevance_weight=3.0, resolution_bonus=3.0)
    selector = NextQuestionSelector(scorer=scorer)

    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S-HIGH", missing_fields=["land_holding_acres"], semantic_score=0.95),
        CandidateSchemeMissingInfo(scheme_id="S-LOW-1", missing_fields=["family_income", "bpl_status"], semantic_score=0.10),
        CandidateSchemeMissingInfo(scheme_id="S-LOW-2", missing_fields=["family_income", "bpl_status"], semantic_score=0.10),
    ]

    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
    )

    # land_holding_acres should win because of high relevance + one-field-away bonus!
    assert res.field == "land_holding_acres"
    assert res.reason_code == QuestionReasonCode.IMMEDIATE_SCHEME_RESOLUTION.value


def test_question_selection_one_field_away_bonus():
    scorer = QuestionScorer(resolution_bonus=5.0)
    selector = NextQuestionSelector(scorer=scorer)

    # Scheme A needs only district (1 field away from decision)
    # Scheme B needs 4 fields
    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S-ONE-AWAY", missing_fields=["district"], semantic_score=0.5),
        CandidateSchemeMissingInfo(
            scheme_id="S-FAR-AWAY",
            missing_fields=["family_income", "social_category", "land_holding_acres", "farmer_category"],
            semantic_score=0.5,
        ),
    ]

    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
    )

    assert res.field == "district"
    assert res.reason_code == QuestionReasonCode.IMMEDIATE_SCHEME_RESOLUTION.value


def test_question_selection_repeat_penalty():
    scorer = QuestionScorer(repeat_penalty=5.0)
    selector = NextQuestionSelector(scorer=scorer)

    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S1", missing_fields=["family_income"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S2", missing_fields=["district"], semantic_score=0.5),
    ]

    # family_income was already asked twice
    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
        field_ask_counts={"family_income": 2, "district": 0},
    )

    # district should win due to repeat penalty on family_income
    assert res.field == "district"


def test_question_selection_sensitivity_tie_breaker():
    # Two candidates with identical frequency and relevance: district (LOW) vs family_income (MEDIUM)
    selector = NextQuestionSelector()

    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S1", missing_fields=["district"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S2", missing_fields=["family_income"], semantic_score=0.5),
    ]

    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
    )

    # district has lower sensitivity penalty than family_income
    assert res.field == "district"


def test_stopping_rule_enough_confirmed_schemes():
    selector = NextQuestionSelector(target_confirmed_schemes=3)

    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S1", missing_fields=["family_income"], semantic_score=0.5),
    ]

    # Already have 3 eligible schemes
    res = selector.select_next_question(
        eligible_schemes_count=3,
        more_info_schemes=more_info,
    )

    assert res.field is None
    assert res.reason_code == QuestionReasonCode.ENOUGH_CONFIRMED_RESULTS.value


def test_stopping_rule_no_candidates():
    selector = NextQuestionSelector()

    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=[],
    )

    assert res.field is None
    assert res.reason_code == QuestionReasonCode.NO_RELEVANT_CANDIDATES.value


def test_stopping_rule_all_declined():
    selector = NextQuestionSelector()

    more_info = [
        CandidateSchemeMissingInfo(scheme_id="S1", missing_fields=["family_income"], semantic_score=0.5),
        CandidateSchemeMissingInfo(scheme_id="S2", missing_fields=["social_category"], semantic_score=0.5),
    ]

    # Both missing fields are declined
    res = selector.select_next_question(
        eligible_schemes_count=0,
        more_info_schemes=more_info,
        declined_fields={"family_income", "social_category"},
    )

    assert res.field is None
    assert res.reason_code == QuestionReasonCode.CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION.value


def test_boolean_or_short_circuit_integration():
    """
    Scheme: BPL OR income <= 200000.
    If citizen has bpl_status=True, Day 14 short-circuits to ELIGIBLE.
    family_income must NOT be listed as missing.
    """
    raw_scheme = make_test_scheme_raw(
        scheme_id="SCHEME-OR-TEST",
        name_en="OR Short Circuit Test",
        root_rule={
            "type": "OR",
            "children": [
                {"condition_id": "C-BPL", "field": "bpl_status", "operator": "EQ", "value": True},
                {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
            ],
        },
    )
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)

    # Citizen is BPL confirmed, income unknown
    profile = CitizenProfile(bpl_status=True)
    res = EligibilityEngine.evaluate_scheme(compiled, profile)

    assert res.eligibility_status == EligibilityStatus.ELIGIBLE
    # No missing fields!
    assert len(res.missing_fields) == 0


def test_boolean_and_short_circuit_integration():
    """
    Scheme: state == 'Rajasthan' AND income <= 200000.
    Citizen has state = 'Gujarat'.
    Result is NOT_ELIGIBLE; scheme is pruned from candidate set.
    """
    raw_scheme = make_test_scheme_raw(
        scheme_id="SCHEME-AND-TEST",
        name_en="AND Short Circuit Test",
        root_rule={
            "type": "AND",
            "children": [
                {"condition_id": "C-STATE", "field": "state", "operator": "EQ", "value": "Rajasthan"},
                {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
            ],
        },
    )
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)

    profile = CitizenProfile(state="Gujarat")
    res = EligibilityEngine.evaluate_scheme(compiled, profile)

    assert res.eligibility_status == EligibilityStatus.NOT_ELIGIBLE


# ===========================================================================
# 4. API & End-to-End Discovery Integration Tests
# ===========================================================================

def test_api_session_lifecycle(test_db):
    # 1. Create Session
    create_res = client.post("/api/v1/citizen/sessions")
    assert create_res.status_code == 201
    data = create_res.json()
    session_id = data["session_id"]
    assert session_id is not None

    # 2. Get Session Summary
    get_res = client.get(f"/api/v1/citizen/sessions/{session_id}")
    assert get_res.status_code == 200
    summary = get_res.json()
    assert summary["session_id"] == session_id
    assert summary["known_fields"] == []

    # 3. Patch Profile
    patch_res = client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 64, "state": "Rajasthan"}},
    )
    assert patch_res.status_code == 200
    p_summary = patch_res.json()
    assert "age" in p_summary["known_fields"]
    assert "state" in p_summary["known_fields"]

    # 4. Detail endpoint
    detail_res = client.get(f"/api/v1/citizen/sessions/{session_id}/profile")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["profile"]["age"] == 64
    assert detail["profile"]["state"] == "Rajasthan"

    # 5. Decline a field
    decline_res = client.post(
        f"/api/v1/citizen/sessions/{session_id}/decline-field",
        json={"field_name": "social_category", "reason": "Prefer not to disclose"},
    )
    assert decline_res.status_code == 200
    d_summary = decline_res.json()
    assert "social_category" in d_summary["declined_fields"]

    # 6. Delete session
    del_res = client.delete(f"/api/v1/citizen/sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 7. Further access returns 404
    assert client.get(f"/api/v1/citizen/sessions/{session_id}").status_code == 404


def test_api_admin_cache_rules():
    res = client.get("/api/v1/admin/cache/rules")
    assert res.status_code == 200
    data = res.json()
    assert "entries" in data
    assert "hits" in data
    assert "misses" in data
    assert "refreshes" in data
    assert "compile_failures" in data


def test_performance_benchmarks(test_db):
    """
    Measures rule cache evaluation latency and question selector throughput.
    """
    cache = get_rule_cache()
    scheme_id = "SCHEME-PERF-01"
    raw_scheme = make_test_scheme_raw(
        scheme_id=scheme_id,
        name_en="Perf Benchmark Scheme",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18},
    )
    compiled = EligibilityRuleCompiler.compile_scheme(raw_scheme)

    from app.cache.verified_rule_cache import CachedRuleEntry
    cache._cache[scheme_id] = CachedRuleEntry(
        scheme_id=scheme_id,
        scheme_version="1.0",
        version_hash="perf-hash",
        compiled_scheme=compiled,
        cached_at=datetime.now(timezone.utc),
    )

    profile = CitizenProfile(age=25)

    # Benchmark 1: 1,000 warm cache evaluations
    t0 = time.perf_counter()
    for _ in range(1000):
        c = cache.get(scheme_id)
        EligibilityEngine.evaluate_scheme(c, profile)
    t1 = time.perf_counter()
    warm_eval_total_ms = (t1 - t0) * 1000.0
    warm_per_eval_us = (warm_eval_total_ms / 1000.0) * 1000.0

    # Benchmark 2: Question selection over 50 candidate schemes
    selector = NextQuestionSelector()
    candidates_50 = [
        CandidateSchemeMissingInfo(
            scheme_id=f"S-{i}",
            missing_fields=["family_income", "district"] if i % 2 == 0 else ["land_holding_acres"],
            semantic_score=0.8 - (i * 0.01),
        )
        for i in range(50)
    ]

    t2 = time.perf_counter()
    for _ in range(100):
        selector.select_next_question(
            eligible_schemes_count=0,
            more_info_schemes=candidates_50,
            known_profile_fields={"state"},
        )
    t3 = time.perf_counter()
    selector_duration_ms = ((t3 - t2) * 1000.0) / 100.0

    print(f"\n[BENCHMARK] 1,000 warm cache evaluations: {round(warm_eval_total_ms, 2)}ms ({round(warm_per_eval_us, 2)}us / eval)")
    print(f"[BENCHMARK] Question selection over 50 candidates: {round(selector_duration_ms, 3)}ms / run")

    assert warm_per_eval_us < 500  # under 0.5ms per evaluation
    assert selector_duration_ms < 10.0  # under 10ms for question selection


def test_session_discovery_api_flow(test_db):
    """
    End-to-end multi-turn session discovery test:
    Turn 1: Citizen provides age 64, state Rajasthan.
            Schemes A and B require family_income.
            Scheme C requires district.
            System identifies family_income as highest-utility question.
    Turn 2: Citizen provides family_income = 120000.
            Schemes A and B immediately become ELIGIBLE!
    """
    # 1. Setup DB metadata
    s1 = SchemeSearchMetadata(
        scheme_id="SCHEME-DISC-01",
        scheme_name="Rajasthan Farmer Subsidy",
        state="Rajasthan",
        districts=[],
        rural_urban="BOTH",
        scheme_origin="RAJASTHAN_STATE",
        category="Agriculture",
        is_active=True,
        is_verified=True,
        search_text="Financial subsidy for farmers in Rajasthan",
        search_text_hash="hash-disc-1",
    )
    s2 = SchemeSearchMetadata(
        scheme_id="SCHEME-DISC-02",
        scheme_name="Rajasthan Small Farmer Grant",
        state="Rajasthan",
        districts=[],
        rural_urban="BOTH",
        scheme_origin="RAJASTHAN_STATE",
        category="Agriculture",
        is_active=True,
        is_verified=True,
        search_text="Agricultural grant for small farmers",
        search_text_hash="hash-disc-2",
    )
    s3 = SchemeSearchMetadata(
        scheme_id="SCHEME-DISC-03",
        scheme_name="Udaipur Senior Citizen Pension",
        state="Rajasthan",
        districts=[],
        rural_urban="BOTH",
        scheme_origin="RAJASTHAN_STATE",
        category="Social Welfare",
        is_active=True,
        is_verified=True,
        search_text="Old age pension in Udaipur district",
        search_text_hash="hash-disc-3",
    )

    # Clean existing if any
    test_db.query(SchemeSearchMetadata).filter(
        SchemeSearchMetadata.scheme_id.in_(["SCHEME-DISC-01", "SCHEME-DISC-02", "SCHEME-DISC-03"])
    ).delete(synchronize_session=False)
    test_db.add_all([s1, s2, s3])
    test_db.commit()

    # 2. Populate compiled rule cache
    cache = get_rule_cache()
    from app.cache.verified_rule_cache import CachedRuleEntry

    r1 = make_test_scheme_raw(
        "SCHEME-DISC-01", "Rajasthan Farmer Subsidy",
        root_rule={
            "type": "AND",
            "children": [
                {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 18},
                {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 150000},
            ],
        }
    )
    r2 = make_test_scheme_raw(
        "SCHEME-DISC-02", "Rajasthan Small Farmer Grant",
        root_rule={
            "type": "AND",
            "children": [
                {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 18},
                {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
            ],
        }
    )
    r3 = make_test_scheme_raw(
        "SCHEME-DISC-03", "Udaipur Senior Citizen Pension",
        root_rule={
            "type": "AND",
            "children": [
                {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 60},
                {"condition_id": "C-DIST", "field": "district", "operator": "EQ", "value": "Udaipur"},
            ],
        }
    )

    for r, sid in [(r1, "SCHEME-DISC-01"), (r2, "SCHEME-DISC-02"), (r3, "SCHEME-DISC-03")]:
        c = EligibilityRuleCompiler.compile_scheme(r)
        cache._cache[sid] = CachedRuleEntry(
            scheme_id=sid,
            scheme_version="1.0",
            version_hash=f"hash-{sid}",
            compiled_scheme=c,
            cached_at=datetime.now(timezone.utc),
        )

    try:
        # Turn 1: Create session
        c_res = client.post("/api/v1/citizen/sessions")
        assert c_res.status_code == 201
        sid = c_res.json()["session_id"]

        # Citizen provides age and state
        p_res = client.patch(
            f"/api/v1/citizen/sessions/{sid}/profile",
            json={"profile": {"age": 64, "state": "Rajasthan"}},
        )
        assert p_res.status_code == 200

        # Discover
        d1_res = client.post(
            f"/api/v1/citizen/sessions/{sid}/discover",
            json={"need_text": "farmer financial subsidy"},
        )
        assert d1_res.status_code == 200
        d1 = d1_res.json()

        # Both agricultural schemes need family_income; scheme 3 needs district
        more_info_ids = [m["scheme_id"] for m in d1["more_information_required"]]
        assert "SCHEME-DISC-01" in more_info_ids
        assert "SCHEME-DISC-02" in more_info_ids
        assert "SCHEME-DISC-03" in more_info_ids

        # Next question MUST be family_income!
        assert d1["next_question"]["field"] == "family_income"
        assert d1["next_question"]["affected_scheme_count"] == 2
        assert "family_income" in d1["session_summary"]["asked_fields"]

        # Turn 2: Citizen answers family_income = 120000
        p2_res = client.patch(
            f"/api/v1/citizen/sessions/{sid}/profile",
            json={"profile": {"family_income": 120000}},
        )
        assert p2_res.status_code == 200

        # Discover again
        d2_res = client.post(
            f"/api/v1/citizen/sessions/{sid}/discover",
            json={"need_text": "farmer financial subsidy"},
        )
        assert d2_res.status_code == 200
        d2 = d2_res.json()

        # SCHEME-DISC-01 and SCHEME-DISC-02 are now ELIGIBLE!
        eligible_ids = [e["scheme_id"] for e in d2["eligible"]]
        assert "SCHEME-DISC-01" in eligible_ids
        assert "SCHEME-DISC-02" in eligible_ids

    finally:
        # Cleanup test metadata
        test_db.query(SchemeSearchMetadata).filter(
            SchemeSearchMetadata.scheme_id.in_(["SCHEME-DISC-01", "SCHEME-DISC-02", "SCHEME-DISC-03"])
        ).delete(synchronize_session=False)
        test_db.commit()

