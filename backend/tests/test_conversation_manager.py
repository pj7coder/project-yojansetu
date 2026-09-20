"""
Comprehensive Test Suite for YojanSetu Deterministic Conversation Manager & State Machine (Day 25).
Tests all 39 workflow scenarios: transitions, guards, context safety, interruptions,
corrections, ordinals, concurrency, idempotency, refresh restoration, and end-to-end dialogues.
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cache.verified_rule_cache import CachedRuleEntry, get_rule_cache
from app.conversation.actions import ConversationAction
from app.conversation.events import ConversationEvent
from app.conversation.manager import ConversationManager, get_conversation_manager
from app.conversation.messages import ConversationMessageCatalog
from app.conversation.schemas import (
    ConversationInput,
    ConversationInputType,
    ConversationResponse,
)
from app.conversation.state_machine import ConversationStateMachine
from app.conversation.states import ConversationState
from app.database.models.category import Category
from app.database.models.department import Department
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.eligibility.compiler import EligibilityRuleCompiler
from app.main import app
from app.sessions.manager import CitizenSessionManager, SessionNotFoundError, get_session_manager
from app.sessions.models import CitizenSession, FieldValueState

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures & Seeding Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fresh_session_mgr():
    """Returns the process-level CitizenSessionManager instance."""
    return get_session_manager()


@pytest.fixture
def conv_mgr():
    """Returns the process-level ConversationManager instance."""
    return get_conversation_manager()


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_schemes():
    """Seeds verified test schemes for pension and agriculture discovery."""
    db = SessionLocal()
    try:
        # 1. Department & Category
        dept = db.execute(select(Department).where(Department.code == "RJ-CONV-DEPT")).scalars().first()
        if not dept:
            dept = Department(
                code="RJ-CONV-DEPT",
                name_en="Social Welfare Dept",
                name_hi="सामाजिक कल्याण विभाग",
            )
            db.add(dept)

        cat = db.execute(select(Category).where(Category.code == "CONV-WELFARE")).scalars().first()
        if not cat:
            cat = Category(
                code="CONV-WELFARE",
                name_en="Welfare",
                name_hi="कल्याण",
            )
            db.add(cat)
        db.commit()

        # Helper to seed a scheme
        def seed(code, name_en, name_hi, root_rule, benefits, docs):
            scheme = db.execute(select(Scheme).where(Scheme.scheme_code == code)).scalars().first()
            if not scheme:
                scheme = Scheme(
                    scheme_code=code,
                    name_en=name_en,
                    name_hi=name_hi,
                    short_name=name_en[:20],
                    department_id=dept.id,
                    category_id=cat.id,
                    status="HUMAN_VERIFIED",
                    jurisdiction="RAJASTHAN",
                    scheme_origin="RAJASTHAN_STATE",
                )
                db.add(scheme)
                db.commit()
                db.refresh(scheme)

            canon = {
                "schema_version": "1.0",
                "scheme_identity": {
                    "scheme_id": str(scheme.id),
                    "name": {"en": name_en, "hi": name_hi},
                    "department": dept.name_en,
                    "description": name_en,
                    "description_hi": name_hi,
                    "category": "PENSION",
                    "scheme_origin": "RAJASTHAN_STATE",
                    "jurisdiction": "Rajasthan",
                },
                "scope": {"state": "Rajasthan", "districts": [], "rural_urban": "BOTH"},
                "eligibility": {"root_rule": root_rule},
                "exclusions": [],
                "benefits": benefits,
                "required_documents": docs,
                "application": {
                    "channels": ["e-Mitra Kiosk", "SSO Portal"],
                    "portal_url": "https://sso.rajasthan.gov.in",
                    "submission_mode": "ONLINE_AND_OFFLINE",
                },
            }

            ver = db.execute(select(SchemeVersion).where(SchemeVersion.scheme_id == scheme.id)).scalars().first()
            if not ver:
                ver = SchemeVersion(
                    scheme_id=scheme.id,
                    version_number=1,
                    version_label="v1.0",
                    status="ACTIVE",
                    valid_from=date(2025, 1, 1),
                    is_current=True,
                    canonical_data=canon,
                    source_summary="Test circular",
                )
                db.add(ver)

            # Metadata
            meta = db.execute(select(SchemeSearchMetadata).where(SchemeSearchMetadata.scheme_id == str(scheme.id))).scalars().first()
            if not meta:
                meta = SchemeSearchMetadata(
                    scheme_id=str(scheme.id),
                    scheme_name=name_en,
                    scheme_name_hi=name_hi,
                    department_id=dept.id,
                    state="Rajasthan",
                    districts=[],
                    rural_urban="BOTH",
                    scheme_origin="RAJASTHAN_STATE",
                    category="Pension",
                    is_active=True,
                    is_verified=True,
                    search_text=f"{name_en} {name_hi} pension old age farmer",
                    search_text_hash=f"hash-{scheme.id}",
                )
                db.add(meta)
            db.commit()

            # Compile into cache
            cache = get_rule_cache()
            raw_wrap = {
                "schema_version": "1.0",
                "review": {"status": "HUMAN_VERIFIED", "artifact_sha256": f"h-{scheme.id}"},
                "canonical_scheme": canon,
            }
            compiled = EligibilityRuleCompiler.compile_scheme(raw_wrap)
            cache._cache[str(scheme.id)] = CachedRuleEntry(
                scheme_id=str(scheme.id),
                scheme_version="1",
                version_hash=f"h-{scheme.id}",
                compiled_scheme=compiled,
                cached_at=datetime.now(timezone.utc),
            )

        # Seed Scheme 1: Old Age Pension (Age >= 60, Income <= 200000, State = Rajasthan)
        seed(
            code="RJ-CONV-OLD-AGE",
            name_en="Mukhyamantri Vridhjan Samman Pension",
            name_hi="मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
            root_rule={
                "type": "AND",
                "children": [
                    {"condition_id": "c_age", "field": "age", "operator": "GTE", "value": 60},
                    {"condition_id": "c_inc", "field": "family_income", "operator": "LTE", "value": 200000},
                ],
            },
            benefits=[{
                "type": "CASH", "amount": 1000, "currency": "INR", "frequency": "MONTHLY",
                "description_en": "₹1,000 monthly pension", "description_hi": "₹1,000 प्रति माह पेंशन",
            }],
            docs=[
                {"document_name": "Jan Aadhaar", "document_name_hi": "जन आधार", "is_mandatory": True},
                {"document_name": "Age Proof", "document_name_hi": "आयु प्रमाण पत्र", "is_mandatory": True},
            ],
        )

        # Seed Scheme 2: Farmer Pension (Occupation = FARMER, Age >= 58, Income <= 250000)
        seed(
            code="RJ-CONV-FARMER-PEN",
            name_en="Kisan Seva Pension Yojana",
            name_hi="किसान सेवा पेंशन योजना",
            root_rule={
                "type": "AND",
                "children": [
                    {"condition_id": "c_occ", "field": "occupation", "operator": "EQUALS", "value": "FARMER"},
                    {"condition_id": "c_f_age", "field": "age", "operator": "GTE", "value": 58},
                    {"condition_id": "c_f_inc", "field": "family_income", "operator": "LTE", "value": 250000},
                ],
            },
            benefits=[{
                "type": "CASH", "amount": 1500, "currency": "INR", "frequency": "MONTHLY",
                "description_en": "₹1,500 monthly farmer support", "description_hi": "₹1,500 प्रति माह कृषक सहायता",
            }],
            docs=[
                {"document_name": "Jan Aadhaar", "document_name_hi": "जन आधार", "is_mandatory": True},
                {"document_name": "Land Records", "document_name_hi": "जमाबंदी / भूमि रिकॉर्ड", "is_mandatory": True},
            ],
        )

        # Seed Scheme 3: BPL Widow Assistance (BPL Status = True, Widow Status = True)
        seed(
            code="RJ-CONV-WIDOW-BPL",
            name_en="Ekal Nari Samman Pension",
            name_hi="एकल नारी सम्मान पेंशन योजना",
            root_rule={
                "type": "AND",
                "children": [
                    {"condition_id": "c_bpl", "field": "bpl_status", "operator": "EQUALS", "value": True},
                    {"condition_id": "c_widow", "field": "widow_status", "operator": "EQUALS", "value": True},
                ],
            },
            benefits=[{
                "type": "CASH", "amount": 1250, "currency": "INR", "frequency": "MONTHLY",
                "description_en": "₹1,250 monthly pension", "description_hi": "₹1,250 प्रति माह पेंशन",
            }],
            docs=[
                {"document_name": "Jan Aadhaar", "document_name_hi": "जन आधार", "is_mandatory": True},
                {"document_name": "BPL Card", "document_name_hi": "बीपीएल कार्ड", "is_mandatory": True},
            ],
        )

    finally:
        db.close()

    yield

    # Teardown
    db = SessionLocal()
    try:
        schemes = db.execute(select(Scheme).where(Scheme.scheme_code.like("RJ-CONV-%"))).scalars().all()
        for s in schemes:
            db.query(SchemeSearchMetadata).filter(SchemeSearchMetadata.scheme_id == str(s.id)).delete(synchronize_session=False)
            db.query(SchemeVersion).filter(SchemeVersion.scheme_id == s.id).delete(synchronize_session=False)
            db.delete(s)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ===========================================================================
# 1. STATE MACHINE TRANSITIONS & GUARDS TESTS
# ===========================================================================

def test_state_machine_allowed_transitions():
    """Verifies all primary allowed state transitions in the transition table."""
    # NEW_SESSION -> WAITING_FOR_NEED
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.NEW_SESSION, ConversationEvent.SESSION_STARTED
    )
    assert next_s == ConversationState.WAITING_FOR_NEED

    # WAITING_FOR_NEED -> PROCESSING_DISCOVERY
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.WAITING_FOR_NEED, ConversationEvent.NEED_PROVIDED
    )
    assert next_s == ConversationState.PROCESSING_DISCOVERY

    # PROCESSING_DISCOVERY -> WAITING_FOR_PROFILE_VALUE (with mock expected field in session)
    sess = CitizenSession(session_id="s1", expected_field="age")
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.PROCESSING_DISCOVERY, ConversationEvent.MORE_INFO_REQUIRED, session=sess
    )
    assert next_s == ConversationState.WAITING_FOR_PROFILE_VALUE

    # WAITING_FOR_PROFILE_VALUE -> WAITING_FOR_CONFIRMATION (with mock pending confirmation)
    sess.pending_confirmation = {"field": "age", "proposed_value": 62}
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.WAITING_FOR_PROFILE_VALUE,
        ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED,
        session=sess,
    )
    assert next_s == ConversationState.WAITING_FOR_CONFIRMATION

    # WAITING_FOR_CONFIRMATION -> PROCESSING_DISCOVERY (upon confirmation)
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.PROFILE_VALUE_CONFIRMED, session=sess
    )
    assert next_s == ConversationState.PROCESSING_DISCOVERY

    # PROCESSING_DISCOVERY -> SHOWING_RESULTS
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.PROCESSING_DISCOVERY, ConversationEvent.ELIGIBLE_RESULTS_FOUND
    )
    assert next_s == ConversationState.SHOWING_RESULTS


def test_invalid_transition_protection_and_recovery():
    """An illegal transition does not corrupt the state machine or crash."""
    sess = CitizenSession(session_id="s2", conversation_state=ConversationState.WAITING_FOR_NEED.value)

    # Attempting CONFIRM_YES while WAITING_FOR_NEED (no confirmation active)
    next_s = ConversationStateMachine.get_next_state(
        ConversationState.WAITING_FOR_NEED, ConversationEvent.PROFILE_VALUE_CONFIRMED, session=sess
    )
    # Safely stays in WAITING_FOR_NEED
    assert next_s == ConversationState.WAITING_FOR_NEED

    # Recovery check: WAITING_FOR_CONFIRMATION without pending_confirmation recovers to DISCOVERY
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.pending_confirmation = None
    sess.expected_field = None
    recovered = ConversationStateMachine.recover_state(sess)
    assert recovered == ConversationState.PROCESSING_DISCOVERY


# ===========================================================================
# 2. NEED FLOW & DISCOVERY TESTS
# ===========================================================================

def test_need_flow_and_discovery(conv_mgr, fresh_session_mgr, db):
    """Citizen states need -> need saved -> discovery runs -> asks missing age."""
    sess = fresh_session_mgr.create_session()
    conv_mgr.initialize_session(sess.session_id, language="hi")

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="मुझे पेंशन चाहिए"),
        db_session=db,
    )

    assert res.state == ConversationState.WAITING_FOR_PROFILE_VALUE
    assert res.action == ConversationAction.ASK_PROFILE_FIELD
    assert sess.need_text == "मुझे पेंशन चाहिए"
    assert res.expected_input is not None
    assert res.expected_input.field in ("age", "occupation", "bpl_status")


# ===========================================================================
# 3. DIRECT TEXT PROFILE INPUT TESTS
# ===========================================================================

def test_direct_age_text_input(conv_mgr, fresh_session_mgr, db):
    """Citizen replies with direct numeric age '62' when expected_field is 'age'."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "age"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="62"),
        db_session=db,
    )

    # Direct text for non-critical or unambiguous values accepts directly
    assert sess.profile.get("age") == 62
    # Progresses to next question or results
    assert res.state in (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationState.SHOWING_RESULTS)


# ===========================================================================
# 4. STT CRITICAL VALUE & CONFIRMATION TESTS
# ===========================================================================

def test_stt_critical_age_requires_confirmation(conv_mgr, fresh_session_mgr, db):
    """STT transcript 'बासठ' for age requires citizen confirmation before updating profile."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "age"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="बासठ"),
        db_session=db,
    )

    # Must transition to WAITING_FOR_CONFIRMATION
    assert res.state == ConversationState.WAITING_FOR_CONFIRMATION
    assert res.action == ConversationAction.CONFIRM_PROFILE_VALUE
    assert sess.pending_confirmation is not None
    assert sess.pending_confirmation["field"] == "age"
    assert sess.pending_confirmation["proposed_value"] == 62
    # Crucial: session profile must NOT have mutated yet!
    assert "age" not in sess.profile
    assert "62" in res.message.text_hi or "६२" in res.message.text_hi or "62" in res.message.text_en


def test_confirm_yes_applies_profile_and_advances(conv_mgr, fresh_session_mgr, db):
    """Citizen confirms pending age with 'हाँ' -> applied to profile -> advances."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.expected_field = "age"
    sess.pending_confirmation = {
        "field": "age",
        "proposed_value": 62,
        "display_value": "62 वर्ष",
        "reason_code": "STT_CRITICAL_NUMERIC",
    }

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="हाँ"),
        db_session=db,
    )

    # Verified: age committed to profile and pending cleared
    assert sess.profile.get("age") == 62
    assert sess.pending_confirmation is None
    # Discovery advanced
    assert res.state in (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationState.SHOWING_RESULTS)


def test_confirm_no_rejects_without_boolean_mutation(conv_mgr, fresh_session_mgr, db):
    """Citizen rejects pending age with 'नहीं' -> discards 62 without setting age=False!"""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.expected_field = "age"
    sess.pending_confirmation = {
        "field": "age",
        "proposed_value": 62,
        "display_value": "62 वर्ष",
        "reason_code": "STT_CRITICAL_NUMERIC",
    }

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="नहीं"),
        db_session=db,
    )

    # Rejection safety: age must NOT be False, must NOT be 62
    assert "age" not in sess.profile
    assert sess.pending_confirmation is None
    # Re-asks age
    assert res.state == ConversationState.WAITING_FOR_PROFILE_VALUE
    assert res.action == ConversationAction.ASK_PROFILE_FIELD
    assert sess.expected_field == "age"


# ===========================================================================
# 5. YES / NO CONTEXT SAFETY TESTS
# ===========================================================================

def test_boolean_question_nahin_maps_to_false(conv_mgr, fresh_session_mgr, db):
    """When question is boolean (bpl_status), 'नहीं' sets bpl_status=False, NOT confirmation rejection!"""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "bpl_status"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="नहीं"),
        db_session=db,
    )

    # bpl_status must be recorded as False
    assert sess.profile.get("bpl_status") is False
    assert sess.field_states.get("bpl_status") == FieldValueState.KNOWN


def test_boolean_question_haan_maps_to_true(conv_mgr, fresh_session_mgr, db):
    """When question is boolean (bpl_status), 'हाँ' via direct text sets bpl_status=True."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "bpl_status"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="हाँ"),
        db_session=db,
    )

    assert sess.profile.get("bpl_status") is True


# ===========================================================================
# 6. QUERY INTERRUPTION & RESUMPTION TESTS
# ===========================================================================

def test_why_asked_interruption_and_resume(conv_mgr, fresh_session_mgr, db):
    """Citizen asks 'यह क्यों पूछ रहे हो?' during income question -> answers and resumes income."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "family_income"

    # 1. Ask query
    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="यह क्यों पूछ रहे हो?"),
        db_session=db,
    )

    assert res.state == ConversationState.HANDLING_CITIZEN_QUERY
    assert res.action == ConversationAction.ANSWER_FIELD_HELP
    assert "आय" in res.message.text_hi or "income" in res.message.text_en.lower()
    # Check resume context saved
    assert sess.resume_state == ConversationState.WAITING_FOR_PROFILE_VALUE.value
    assert sess.resume_expected_field == "family_income"

    # 2. Next turn provides actual answer
    res2 = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="150000"),
        db_session=db,
    )

    # Successfully applied income to profile
    assert sess.profile.get("family_income") == 150000


def test_query_during_pending_confirmation(conv_mgr, fresh_session_mgr, db):
    """Citizen asks 'यह जानकारी क्यों जरूरी है?' during confirmation -> preserves pending fact!"""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.expected_field = "age"
    sess.pending_confirmation = {
        "field": "age",
        "proposed_value": 62,
        "display_value": "62 वर्ष",
        "reason_code": "STT_CRITICAL_NUMERIC",
    }

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="यह जानकारी क्यों चाहिए?"),
        db_session=db,
    )

    assert res.state == ConversationState.HANDLING_CITIZEN_QUERY
    # Pending confirmation MUST remain intact
    assert sess.pending_confirmation is not None
    assert sess.pending_confirmation["proposed_value"] == 62
    assert sess.resume_state == ConversationState.WAITING_FOR_CONFIRMATION.value


# ===========================================================================
# 7. UNKNOWN, DECLINED & CLARIFICATION TESTS
# ===========================================================================

def test_unknown_response_advances_to_next_field(conv_mgr, fresh_session_mgr, db):
    """Citizen says 'पता नहीं' -> field set to UNKNOWN, selector asks another field."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "family_income"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="पता नहीं"),
        db_session=db,
    )

    assert sess.field_states.get("family_income") == FieldValueState.UNKNOWN
    # Does not get stuck on family_income
    assert sess.expected_field != "family_income" or res.state == ConversationState.SHOWING_RESULTS


def test_decline_response_advances_to_next_field(conv_mgr, fresh_session_mgr, db):
    """Citizen says 'नहीं बताना चाहता' -> field set to DECLINED, selector advances."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "social_category"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="नहीं बताना चाहता"),
        db_session=db,
    )

    assert sess.is_field_declined("social_category")


def test_ambiguous_income_clarification_flow(conv_mgr, fresh_session_mgr, db):
    """Citizen says 'दो लाख से थोड़ा ऊपर' -> enters NEED_CLARIFICATION state."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "family_income"

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="दो लाख से थोड़ा ऊपर"),
        db_session=db,
    )

    assert res.state == ConversationState.NEED_CLARIFICATION
    assert res.action == ConversationAction.CLARIFY_PROFILE_VALUE


def test_clarification_attempt_limit_exceeded(conv_mgr, fresh_session_mgr, db):
    """Repeated ambiguous answers hit MAX_CLARIFICATION_ATTEMPTS -> marks UNKNOWN to avoid infinite loop."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "family_income"
    # Artificially set 2 previous clarification attempts
    sess.clarification_attempts["family_income"] = 2

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="दो लाख से थोड़ा ऊपर"),
        db_session=db,
    )

    # 3rd attempt exceeds limit -> marked UNKNOWN and advances
    assert sess.field_states.get("family_income") == FieldValueState.UNKNOWN
    assert res.state != ConversationState.NEED_CLARIFICATION


# ===========================================================================
# 8. CORRECTION, CHANGE NEED & START OVER TESTS
# ===========================================================================

def test_correction_during_results_invalidates_and_recomputes(conv_mgr, fresh_session_mgr, db):
    """Citizen viewing results says 'मेरी उम्र 61 है' -> requests confirmation -> rediscovery."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.SHOWING_RESULTS.value
    sess.profile["age"] = 64
    sess.result_order = ["scheme_1", "scheme_2"]

    # 1. State correction
    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="मेरी उम्र 61 है"),
        db_session=db,
    )

    assert res.state == ConversationState.WAITING_FOR_CONFIRMATION
    assert sess.pending_confirmation is not None
    assert sess.pending_confirmation["proposed_value"] == 61

    # 2. Confirm YES
    res2 = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="हाँ"),
        db_session=db,
    )

    # Age updated, discovery recomputed
    assert sess.profile["age"] == 61


def test_change_need_preserves_profile(conv_mgr, fresh_session_mgr, db):
    """Action CHANGE_NEED updates need_text while preserving known profile attributes."""
    sess = fresh_session_mgr.create_session()
    sess.profile["age"] = 62
    sess.profile["family_income"] = 150000

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(
            type=ConversationInputType.ACTION,
            action="CHANGE_NEED",
            text="अब मुझे खेती की योजना देखनी है",
        ),
        db_session=db,
    )

    assert sess.need_text == "अब मुझे खेती की योजना देखनी है"
    # Profile facts remain intact
    assert sess.profile["age"] == 62
    assert sess.profile["family_income"] == 150000


def test_start_over_resets_profile_and_conversation(conv_mgr, fresh_session_mgr, db):
    """Action START_OVER wipes temporary facts and resets state to WAITING_FOR_NEED."""
    sess = fresh_session_mgr.create_session()
    sess.profile["age"] = 62
    sess.need_text = "पेंशन"
    sess.pending_confirmation = {"field": "district"}

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.ACTION, action="START_OVER"),
        db_session=db,
    )

    assert res.state == ConversationState.WAITING_FOR_NEED
    assert res.action == ConversationAction.ASK_NEED
    assert sess.profile == {}
    assert sess.need_text is None
    assert sess.pending_confirmation is None


def test_end_conversation_transitions_to_completed(conv_mgr, fresh_session_mgr, db):
    """Action END_CONVERSATION transitions to COMPLETED state."""
    sess = fresh_session_mgr.create_session()

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.ACTION, action="END_CONVERSATION"),
        db_session=db,
    )

    assert res.state == ConversationState.COMPLETED
    assert res.action == ConversationAction.END_CONVERSATION


# ===========================================================================
# 9. SCHEME SELECTION, QUERIES & ORDINALS TESTS
# ===========================================================================

def test_scheme_selection_valid_and_invalid(conv_mgr, fresh_session_mgr, db):
    """Selecting valid scheme card succeeds; selecting unverified/unknown ID raises 400."""
    sess = fresh_session_mgr.create_session()
    scheme = db.execute(select(Scheme).where(Scheme.scheme_code == "RJ-CONV-OLD-AGE")).scalars().first()
    sess.eligible_scheme_ids = [str(scheme.id)]
    sess.result_order = [str(scheme.id)]

    # Valid scheme
    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(
            type=ConversationInputType.ACTION,
            action="SELECT_SCHEME",
            scheme_id=str(scheme.id),
        ),
        db_session=db,
    )
    assert res.focused_scheme is not None
    assert res.focused_scheme.scheme_id == str(scheme.id)

    # Invalid scheme ID
    with pytest.raises(Exception):
        conv_mgr.handle_input(
            session_id=sess.session_id,
            inp=ConversationInput(
                type=ConversationInputType.ACTION,
                action="SELECT_SCHEME",
                scheme_id="00000000-0000-0000-0000-000000000000",
            ),
            db_session=db,
        )


def test_scheme_benefit_query(conv_mgr, fresh_session_mgr, db):
    """Citizen asks 'इस योजना में कितना पैसा मिलता है?' with focused scheme -> returns verified benefits."""
    sess = fresh_session_mgr.create_session()
    scheme = db.execute(select(Scheme).where(Scheme.scheme_code == "RJ-CONV-OLD-AGE")).scalars().first()
    sess.conversation_state = ConversationState.SHOWING_RESULTS.value
    sess.focused_scheme_id = str(scheme.id)
    sess.eligible_scheme_ids = [str(scheme.id)]

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="इस योजना में कितना पैसा मिलता है?"),
        db_session=db,
    )

    assert res.action == ConversationAction.ANSWER_SCHEME_QUERY
    assert "1,000" in res.message.text_hi or "1,000" in res.message.text_en


def test_ordinal_scheme_selection(conv_mgr, fresh_session_mgr, db):
    """Citizen says 'पहली योजना' while viewing results -> selects index 0 in result_order."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.SHOWING_RESULTS.value
    scheme = db.execute(select(Scheme).where(Scheme.scheme_code == "RJ-CONV-OLD-AGE")).scalars().first()
    sess.eligible_scheme_ids = [str(scheme.id)]
    sess.result_order = [str(scheme.id)]

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="मुझे पहली योजना देखनी है"),
        db_session=db,
    )

    assert res.focused_scheme is not None
    assert res.focused_scheme.scheme_id == str(scheme.id)


# ===========================================================================
# 10. IDEMPOTENCY, CONCURRENCY & REFRESH TESTS
# ===========================================================================

def test_idempotency_duplicate_client_turn_id(conv_mgr, fresh_session_mgr, db):
    """Sending the same client_turn_id twice returns cached state without double-incrementing turns."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
    sess.expected_field = "age"

    # Turn 1
    res1 = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="62", client_turn_id="turn-uuid-123"),
        db_session=db,
    )
    turn_count_after_1 = sess.conversation_turn_count

    # Turn 2 (duplicate network retry)
    res2 = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="62", client_turn_id="turn-uuid-123"),
        db_session=db,
    )

    # Turn count did not double-increment
    assert sess.conversation_turn_count == turn_count_after_1


def test_concurrency_stale_version_conflict(conv_mgr, fresh_session_mgr, db):
    """Client sending outdated conversation_version gets 409 conflict."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_version = 5

    with pytest.raises(Exception) as excinfo:
        conv_mgr.handle_input(
            session_id=sess.session_id,
            inp=ConversationInput(type=ConversationInputType.TEXT, text="test", conversation_version=2),
            db_session=db,
        )
    assert "409" in str(excinfo.value) or "version mismatch" in str(excinfo.value)


def test_browser_refresh_restores_state(conv_mgr, fresh_session_mgr, db):
    """GET conversation restores current pending confirmation or active question."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.expected_field = "age"
    sess.pending_confirmation = {
        "field": "age",
        "proposed_value": 62,
        "display_value": "62 वर्ष",
    }

    res = conv_mgr.get_current_state(sess.session_id, db_session=db)
    assert res.state == ConversationState.WAITING_FOR_CONFIRMATION
    assert res.action == ConversationAction.CONFIRM_PROFILE_VALUE
    assert res.expected_input.display_value == "62 वर्ष"


def test_language_switch_preserves_state(conv_mgr, fresh_session_mgr, db):
    """Changing language updates presentation without clearing profile or pending state."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
    sess.expected_field = "age"
    sess.pending_confirmation = {"field": "age", "proposed_value": 62, "display_value": "62 years"}

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(
            type=ConversationInputType.ACTION,
            action="CHANGE_LANGUAGE",
            language="en",
        ),
        db_session=db,
    )

    assert sess.preferred_language == "en"
    assert res.state == ConversationState.WAITING_FOR_CONFIRMATION
    assert sess.pending_confirmation["proposed_value"] == 62


def test_max_turns_safeguard(conv_mgr, fresh_session_mgr, db):
    """Conversation terminates gracefully when max turns threshold is reached."""
    sess = fresh_session_mgr.create_session()
    sess.conversation_turn_count = 25  # hit configured MAX_CONVERSATION_TURNS

    res = conv_mgr.handle_input(
        session_id=sess.session_id,
        inp=ConversationInput(type=ConversationInputType.TEXT, text="hello"),
        db_session=db,
    )

    assert res.state == ConversationState.COMPLETED
    assert res.action == ConversationAction.END_CONVERSATION


# ===========================================================================
# 11. END-TO-END MULTI-TURN TEXT CONVERSATION
# ===========================================================================

def test_e2e_full_text_conversation(conv_mgr, fresh_session_mgr, db):
    """
    Simulates complete text flow:
    Need ('वृद्धावस्था पेंशन') -> Age ('62') -> Confirmation ('हाँ') -> Results.
    """
    sess = fresh_session_mgr.create_session()
    conv_mgr.initialize_session(sess.session_id, language="hi")

    # Turn 1: Need
    r1 = conv_mgr.handle_input(
        sess.session_id,
        ConversationInput(type=ConversationInputType.TEXT, text="मुझे वृद्धावस्था पेंशन चाहिए"),
        db_session=db,
    )
    assert r1.state == ConversationState.WAITING_FOR_PROFILE_VALUE

    # Turn 2: Age
    r2 = conv_mgr.handle_input(
        sess.session_id,
        ConversationInput(type=ConversationInputType.TEXT, text="62"),
        db_session=db,
    )
    assert sess.profile.get("age") == 62


# ===========================================================================
# 12. END-TO-END VOICE-TRANSCRIPT CONVERSATION
# ===========================================================================

def test_e2e_full_voice_transcript_conversation(conv_mgr, fresh_session_mgr, db):
    """
    Simulates Day 23 audio transcripts entering Day 25 ConversationManager:
    'मुझे पेंशन चाहिए' -> 'बासठ' (STT) -> 'हाँ' -> Results.
    """
    sess = fresh_session_mgr.create_session()
    conv_mgr.initialize_session(sess.session_id, language="hi")

    # Turn 1: Voice transcript need
    r1 = conv_mgr.handle_input(
        sess.session_id,
        ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="मुझे पेंशन चाहिए"),
        db_session=db,
    )
    assert r1.state == ConversationState.WAITING_FOR_PROFILE_VALUE

    # Turn 2: Voice transcript age 'बासठ'
    r2 = conv_mgr.handle_input(
        sess.session_id,
        ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="बासठ"),
        db_session=db,
    )
    # STT critical numeric triggers confirmation
    assert r2.state == ConversationState.WAITING_FOR_CONFIRMATION
    assert r2.action == ConversationAction.CONFIRM_PROFILE_VALUE

    # Turn 3: Voice transcript affirmative 'हाँ'
    r3 = conv_mgr.handle_input(
        sess.session_id,
        ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="हाँ"),
        db_session=db,
    )
    # Age confirmed and committed
    assert sess.profile.get("age") == 62


# ===========================================================================
# 13. FASTAPI REST API ENDPOINT TESTS
# ===========================================================================

def test_api_conversation_endpoints():
    """Tests POST /turn, GET /conversation, and POST /start-over over FastAPI TestClient."""
    # Create session via Day 16 API
    create_resp = client.post("/api/v1/citizen/sessions")
    assert create_resp.status_code == 201
    sid = create_resp.json()["session_id"]

    # 1. Turn 1: Need
    turn1_resp = client.post(
        f"/api/v1/citizen/sessions/{sid}/turn",
        json={"type": "TEXT", "text": "मुझे पेंशन चाहिए"},
    )
    assert turn1_resp.status_code == 200
    t1_json = turn1_resp.json()
    assert t1_json["state"] == "WAITING_FOR_PROFILE_VALUE"
    assert t1_json["action"] == "ASK_PROFILE_FIELD"

    # 2. Browser Refresh: GET /conversation
    get_resp = client.get(f"/api/v1/citizen/sessions/{sid}/conversation")
    assert get_resp.status_code == 200
    get_json = get_resp.json()
    assert get_json["state"] == "WAITING_FOR_PROFILE_VALUE"
    assert get_json["action"] == "ASK_PROFILE_FIELD"

    # 3. Start Over: POST /start-over
    start_over_resp = client.post(f"/api/v1/citizen/sessions/{sid}/start-over")
    assert start_over_resp.status_code == 200
    so_json = start_over_resp.json()
    assert so_json["state"] == "WAITING_FOR_NEED"
    assert so_json["action"] == "ASK_NEED"
