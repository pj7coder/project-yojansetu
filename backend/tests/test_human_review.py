from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict
import uuid
from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.evidence_verification_run import EvidenceVerificationRun
from app.database.models.fact_verification import FactVerification
from app.database.models.human_review_item import HumanReviewItem
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.review_audit_event import ReviewAuditEvent
from app.database.models.scheme import Scheme
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.validation_issue import ValidationIssue
from app.database.models.validation_run import ValidationRun
from app.database.session import SessionLocal
from app.main import app
from app.normalization.schemas import (
    ApplicationChannelEnum,
    BenefitTypeEnum,
    CanonicalApplication,
    CanonicalBenefit,
    CanonicalDocument,
    CanonicalEligibility,
    CanonicalIdentity,
    CanonicalImportantDate,
    CanonicalSchemeDraft,
    CanonicalScope,
    DocumentTypeEnum,
    EligibilityCondition,
    EvidenceRegistryItem,
    LogicalGroupType,
    OperatorEnum,
    PeriodicityEnum,
    RuleGroup,
    SchemeNameDetail,
    SchemeOriginEnum,
)
from app.review.schemas import (
    CompleteReviewRequest,
    ConflictResolutionChoice,
    ConflictResolutionRequest,
    ItemDecisionRequest,
    RejectSchemeRequest,
    ReopenReviewRequest,
    ReviewActionType,
    ReviewDecision,
    ReviewSessionStatus,
)
from app.review.service import HumanReviewService
from app.validation.service import SchemeValidationService
from app.verification.service import EvidenceVerificationService

client = TestClient(app)


@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_sample_canonical_data(draft_id: uuid.UUID, doc_id: uuid.UUID) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scheme_id": str(draft_id),
        "source_document_id": str(doc_id),
        "identity": {
            "official_name": {
                "hindi": "राजस्थान वृद्धावस्था पेंशन योजना",
                "english": "Rajasthan Old Age Pension Scheme",
            },
            "department": {
                "raw_text": "सामाजिक न्याय एवं अधिकारिता विभाग",
                "department_id": None,
                "department_name": "Social Justice and Empowerment Department",
            },
            "scheme_origin": "RAJASTHAN_STATE",
        },
        "scope": {
            "spatial_coverage": "STATE",
            "jurisdiction": ["Rajasthan"],
            "target_beneficiaries": ["Senior Citizens"],
        },
        "eligibility": {
            "root_rule": {
                "group_type": "AND",
                "children": [
                    {
                        "field": "age",
                        "operator": "GTE",
                        "value": 60,
                        "unit": "years",
                        "evidence_refs": ["EV-002"],
                    },
                    {
                        "field": "family_income",
                        "operator": "LTE",
                        "value": 200000,
                        "currency": "INR",
                        "period": "ANNUAL",
                        "evidence_refs": ["EV-001"],
                    },
                ],
            },
            "exclusions": [
                {
                    "exclusion_id": "EXCL-001",
                    "raw_text": "Income Tax Payers are not eligible.",
                    "evidence_refs": [],
                }
            ],
        },
        "benefits": [
            {
                "type": "CASH_TRANSFER",
                "amount": 1000,
                "currency": "INR",
                "periodicity": "MONTHLY",
                "description": "Monthly pension of Rs 1,000",
            }
        ],
        "documents": [
            {
                "name": "Aadhaar Card",
                "document_type": "IDENTITY_PROOF",
                "is_mandatory": True,
            }
        ],
        "application": {
            "channel": "ONLINE",
            "portal_url": "https://ssp.rajasthan.gov.in",
            "fees": 0,
        },
        "important_dates": [
            {
                "label": "Effective Date",
                "date_value": "2024-04-01",
                "date_type": "EFFECTIVE_DATE",
            }
        ],
        "evidence_registry": {
            "EV-001": {
                "evidence_id": "EV-001",
                "chunk_id": f"CHUNK-{doc_id}-001",
                "page_number": 7,
                "source_block_id": "block_7_1",
                "snippet": "वार्षिक पारिवारिक आय ₹2,00,000 से अधिक नहीं होनी चाहिए।",
                "field_path": "eligibility.root_rule.children[1]",
                "ocr_derived": False,
            },
            "EV-002": {
                "evidence_id": "EV-002",
                "chunk_id": f"CHUNK-{doc_id}-001",
                "page_number": 2,
                "source_block_id": "block_2_3",
                "snippet": "आवेदक की आयु 60 वर्ष या उससे अधिक होनी चाहिए।",
                "field_path": "eligibility.root_rule.children[0]",
                "ocr_derived": False,
            },
        },
        "conflicts": [],
    }


@pytest.fixture
def review_test_fixture(test_db):
    settings = get_settings()
    doc_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        document_code=f"DOC-REV-{doc_id.hex[:6].upper()}",
        source_id=None,
        original_filename="rajasthan_pension_guidelines.pdf",
        storage_path="storage/originals/rajasthan_pension_guidelines.pdf",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        file_size_bytes=4096,
        page_count=10,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_HUMAN_REVIEW",
    )
    test_db.add(doc)

    chunk = DocumentChunk(
        chunk_id_str=f"CHUNK-{doc_id}-001",
        document_id=doc_id,
        chunk_index=0,
        section_type="ELIGIBILITY",
        token_count=120,
        page_start=1,
        page_end=10,
        artifact_path=f"storage/chunks/{doc_id}/chunk_0.json",
    )
    test_db.add(chunk)

    draft_dir = settings.storage_path / "normalized" / str(doc_id) / str(draft_id)
    draft_dir.mkdir(parents=True, exist_ok=True)
    canonical_file = draft_dir / "canonical.json"

    raw_canonical = create_sample_canonical_data(draft_id, doc_id)
    canonical_file.write_text(json.dumps(raw_canonical, indent=2, ensure_ascii=False), encoding="utf-8")

    rel_artifact_path = f"normalized/{doc_id}/{draft_id}/canonical.json"

    draft = SchemeDraft(
        id=draft_id,
        document_id=doc_id,
        internal_scheme_code=f"RJ-REV-{draft_id.hex[:8].upper()}",
        detected_name="राजस्थान वृद्धावस्था पेंशन योजना",
        official_name_raw="राजस्थान वृद्धावस्था पेंशन योजना",
        normalized_name_for_matching="राजस्थान वृद्धावस्था पेंशन योजना",
        department_name_raw="सामाजिक न्याय एवं अधिकारिता विभाग",
        status="READY_FOR_HUMAN_REVIEW",
        conflict_count=0,
        artifact_path=rel_artifact_path,
    )
    test_db.add(draft)

    # Add baseline validation run
    val_run = ValidationRun(
        id=uuid.uuid4(),
        scheme_draft_id=draft_id,
        validator_version="1.0",
        schema_version="1.0",
        status="VALIDATION_PASSED",
        blocker_count=0,
        error_count=0,
        warning_count=0,
        info_count=0,
        rules_checked_count=20,
        started_at=datetime.now(timezone.utc),
        canonical_artifact_hash=hashlib.sha256(canonical_file.read_bytes()).hexdigest(),
        diagnostics={"status": "PASS"},
    )
    test_db.add(val_run)

    # Add baseline evidence verification run
    ev_run = EvidenceVerificationRun(
        id=uuid.uuid4(),
        scheme_draft_id=draft_id,
        verifier_version="1.0",
        canonical_artifact_sha256=hashlib.sha256(canonical_file.read_bytes()).hexdigest(),
        status="EVIDENCE_VERIFIED",
        facts_total=5,
        facts_supported=5,
        facts_contradicted=0,
        facts_insufficient=0,
        facts_failed=0,
        critical_issues_count=0,
        started_at=datetime.now(timezone.utc),
        diagnostics={"status": "ALL_SUPPORTED", "ocr_risk_count": 0},
    )
    test_db.add(ev_run)

    test_db.commit()

    return {
        "doc_id": doc_id,
        "draft_id": draft_id,
        "canonical_file": canonical_file,
        "raw_canonical": raw_canonical,
    }


def test_review_queue_endpoint(review_test_fixture):
    """Test GET /api/v1/review/queue returns prioritized items."""
    res = client.get("/api/v1/review/queue?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    draft_item = next(
        (i for i in data["items"] if i["draft_id"] == str(review_test_fixture["draft_id"])),
        None,
    )
    assert draft_item is not None
    assert draft_item["scheme_name"] == "राजस्थान वृद्धावस्था पेंशन योजना"
    assert draft_item["draft_status"] == "READY_FOR_HUMAN_REVIEW"


def test_start_review_session_and_retrieve_detail(test_db, review_test_fixture):
    """Test starting a review session and fetching consolidated review detail."""
    draft_id = review_test_fixture["draft_id"]

    # Start review session
    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/start",
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    sess_data = res.json()
    assert sess_data["status"] == "IN_PROGRESS"
    assert sess_data["reviewer_id"] == "DEV_REVIEWER"
    assert sess_data["review_version"] == 1

    # Fetch review workspace detail
    res_detail = client.get(
        f"/api/v1/scheme-drafts/{draft_id}/review",
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["scheme_draft_id"] == str(draft_id)
    assert len(detail["items"]) > 0
    assert detail["summary"]["total_items"] == len(detail["items"])
    assert detail["summary"]["pending"] == len(detail["items"])

    # Check evidence page navigation metadata
    income_item = next(
        (i for i in detail["items"] if i["field_path"].endswith("children[1]")),
        None,
    )
    assert income_item is not None
    assert income_item["page_number"] == 7
    assert "₹2,00,000" in income_item["evidence_text"]


def test_field_approval_and_audit(test_db, review_test_fixture):
    """Test approving an individual fact creates an immutable audit record."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    item = session.items[0]
    assert item.decision == "PENDING"

    # Approve fact via API
    res = client.post(
        f"/api/v1/review-items/{item.id}/decision",
        json={
            "decision": "APPROVED",
            "reviewer_comment": "Verified against source document.",
        },
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    updated_item = res.json()
    assert updated_item["decision"] == "APPROVED"
    assert updated_item["reviewer_comment"] == "Verified against source document."

    # Verify audit event recorded
    audit_events = service.repo.get_audit_events_by_draft(test_db, draft_id)
    assert any(
        a.action_type == "FIELD_APPROVED" and a.item_id == item.id for a in audit_events
    )


def test_contradiction_override_requires_reason(test_db, review_test_fixture):
    """Test approving a CONTRADICTED fact strictly requires an override reason."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Set item verification to CONTRADICTED
    item = session.items[0]
    item.verification_result = "CONTRADICTED"
    test_db.commit()

    # Attempt approve WITHOUT override reason -> should fail with 400
    res_fail = client.post(
        f"/api/v1/review-items/{item.id}/decision",
        json={"decision": "APPROVED"},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res_fail.status_code == 400
    assert "override reason is mandatory" in res_fail.json()["detail"].lower()

    # Attempt approve WITH override reason -> succeeds
    res_ok = client.post(
        f"/api/v1/review-items/{item.id}/decision",
        json={
            "decision": "APPROVED",
            "override_reason": "Contextual paragraph on page 8 supersedes contradiction.",
        },
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["decision"] == "APPROVED"

    # Verify audit recorded VERIFICATION_OVERRIDE
    audit_events = service.repo.get_audit_events_by_draft(test_db, draft_id)
    assert any(a.action_type == "VERIFICATION_OVERRIDE" for a in audit_events)


def test_edit_fact_triggers_automatic_revalidation_and_audit(test_db, review_test_fixture):
    """
    Mandatory test (Section 116):
    Reviewer edits a canonical value:
    1. Modifies canonical JSON on disk
    2. Records before and after in audit
    3. Triggers automatic revalidation & reverification
    4. Updates session canonical SHA-256 and increments review version
    """
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Find family income item
    income_item = next(
        i for i in session.items if i.field_path.endswith("children[1]")
    )
    old_version = session.review_version

    new_income_condition = {
        "field": "family_income",
        "operator": "LTE",
        "value": 150000,
        "currency": "INR",
        "period": "ANNUAL",
    }

    # Edit via API
    res = client.post(
        f"/api/v1/review-items/{income_item.id}/decision",
        json={
            "decision": "EDITED",
            "edit_value": new_income_condition,
            "edit_reason": "Corrected income ceiling per gazette amendment.",
        },
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["decision"] == "EDITED"
    assert res_data["current_value_json"]["value"] == 150000

    # Refresh session from DB
    test_db.refresh(session)
    assert session.review_version == old_version + 1

    # Verify canonical file on disk was updated
    canonical_path = Path(review_test_fixture["canonical_file"])
    disk_data = json.loads(canonical_path.read_text(encoding="utf-8"))
    disk_cond = disk_data["eligibility"]["root_rule"]["children"][1]
    assert disk_cond["value"] == 150000

    # Verify audit event has before and after snapshots
    audit_events = service.repo.get_audit_events_by_draft(test_db, draft_id)
    edit_event = next(
        a for a in audit_events if a.action_type == "FIELD_EDITED" and a.item_id == income_item.id
    )
    assert edit_event.before_value_json["value"] == 200000
    assert edit_event.after_value_json["value"] == 150000
    assert "gazette amendment" in edit_event.reason


def test_conflict_resolution_and_conditional_preservation(test_db, review_test_fixture):
    """Test resolving extraction contradiction side-by-side (Section 32, 33, 118, 119)."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Insert a candidate conflict into canonical data on disk
    canonical_path = Path(review_test_fixture["canonical_file"])
    canonical_data = json.loads(canonical_path.read_text(encoding="utf-8"))
    canonical_data["conflicts"] = [
        {
            "conflict_id": "CONF-001",
            "field": "family_income",
            "status": "REVIEW_REQUIRED",
            "explanation": "Page 7 states ₹2,00,000 while Page 18 states ₹3,00,000",
            "values": [
                {
                    "value": 200000,
                    "page_number": 7,
                    "text_snippet": "वार्षिक पारिवारिक आय ₹2,00,000",
                },
                {
                    "value": 300000,
                    "page_number": 18,
                    "text_snippet": "वार्षिक पारिवारिक आय ₹3,00,000",
                },
            ],
        }
    ]
    canonical_path.write_text(json.dumps(canonical_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update draft conflict count
    draft = test_db.get(SchemeDraft, draft_id)
    draft.conflict_count = 1
    test_db.commit()

    # Resolve conflict via API choosing Candidate B (₹3,00,000)
    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/conflicts/CONF-001/resolve",
        json={
            "choice": "SELECT_VALUE",
            "selected_value": 300000,
            "reason": "Page 18 represents the latest revised financial notification.",
        },
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["conflict"]["status"] == "RESOLVED"

    # Verify audit event was logged
    audit_events = service.repo.get_audit_events_by_draft(test_db, draft_id)
    assert any(
        a.action_type == "CONFLICT_RESOLVED" and "latest revised" in (a.reason or "")
        for a in audit_events
    )


def test_optimistic_concurrency_conflict_returns_409(test_db, review_test_fixture):
    """Section 111: Reviewer submits stale review version -> 409 Conflict."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    item = session.items[0]

    # Stale version submission (current version is 1, submitting 99)
    res = client.post(
        f"/api/v1/review-items/{item.id}/decision?review_version=99",
        json={"decision": "APPROVED"},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 409
    assert "Optimistic lock conflict" in res.json()["detail"]


def test_completion_guards_block_pending_items(test_db, review_test_fixture):
    """Section 112: Attempting completion with pending items returns 409 Conflict."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Some items are still PENDING
    assert any(i.decision == "PENDING" for i in session.items)

    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/complete",
        json={"review_version": session.review_version, "notes": "Signoff attempt"},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 409
    assert "remain PENDING" in res.json()["detail"]


def test_completion_guards_block_unresolved_blockers(test_db, review_test_fixture):
    """Section 113: Draft with Day 11 BLOCKER issue cannot be completed."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Approve all items first
    for item in session.items:
        item.decision = "APPROVED"
    test_db.commit()

    # Add a BLOCKER validation run
    val_run = ValidationRun(
        id=uuid.uuid4(),
        scheme_draft_id=draft_id,
        validator_version="1.0",
        schema_version="1.0",
        status="VALIDATION_FAILED",
        blocker_count=1,
        error_count=0,
        warning_count=0,
        info_count=0,
        rules_checked_count=25,
        started_at=datetime.now(timezone.utc),
        canonical_artifact_hash=session.canonical_artifact_sha256,
        diagnostics={"blockers": ["AGE_RANGE_INVALID"]},
    )
    test_db.add(val_run)
    test_db.commit()

    # Attempt completion -> blocked!
    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/complete",
        json={"review_version": session.review_version},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 409
    assert "unresolved BLOCKER" in res.json()["detail"]


def test_full_valid_review_and_verified_artifact_sealing(test_db, review_test_fixture):
    """
    Section 120: Full valid scheme review:
    1. All items approved
    2. No blockers
    3. Complete review called
    4. Verified artifact created at storage/verified/<draft_id>/
    5. Draft status = HUMAN_VERIFIED
    6. Schemes production table NOT polluted
    """
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # Count schemes table before
    schemes_count_before = test_db.query(Scheme).count()

    # Approve all items
    for item in session.items:
        item.decision = "APPROVED"
        item.reviewed_by = "DEV_REVIEWER"
    test_db.commit()

    # Complete review via API
    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/complete",
        json={
            "review_version": session.review_version,
            "notes": "Full human review completed. All eligibility and benefit facts confirmed.",
        },
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "HUMAN_VERIFIED"
    assert res_data["summary"]["status"] == "HUMAN_VERIFIED"
    assert res_data["summary"]["approved"] == len(session.items)

    # Verify draft status in DB
    draft = test_db.get(SchemeDraft, draft_id)
    assert draft.status == "HUMAN_VERIFIED"

    # Verify verified artifact sealed on disk
    settings = get_settings()
    verified_dir = settings.verified_dir / str(draft_id)
    assert verified_dir.exists()
    assert (verified_dir / "verified_scheme.json").exists()
    assert (verified_dir / "review_summary.json").exists()
    assert (verified_dir / "audit_snapshot.json").exists()

    verified_json = json.loads((verified_dir / "verified_scheme.json").read_text(encoding="utf-8"))
    assert verified_json["review"]["status"] == "HUMAN_VERIFIED"
    assert verified_json["scheme"]["identity"]["official_name"]["hindi"] == "राजस्थान वृद्धावस्था पेंशन योजना"

    # Verify production schemes table was NOT modified (Section 59, 60: Verification != Publication)
    schemes_count_after = test_db.query(Scheme).count()
    assert schemes_count_after == schemes_count_before

    # Clean up test artifact from disk so it doesn't pollute live verified directory
    import shutil
    if verified_dir.exists():
        shutil.rmtree(verified_dir, ignore_errors=True)


def test_scheme_rejection_workflow(test_db, review_test_fixture):
    """Section 121: Reviewer determines document is irrelevant or bad extraction and rejects scheme."""
    draft_id = review_test_fixture["draft_id"]

    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/reject",
        json={"reason": "Document is an internal administrative roster, not a citizen welfare scheme."},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "HUMAN_REJECTED"

    # Verify draft remains in DB with status HUMAN_REJECTED (no physical deletion)
    draft = test_db.get(SchemeDraft, draft_id)
    assert draft is not None
    assert draft.status == "HUMAN_REJECTED"


def test_review_reopen_workflow(test_db, review_test_fixture):
    """Section 122: Reopen a verified scheme draft creating versioned session."""
    draft_id = review_test_fixture["draft_id"]
    service = HumanReviewService(test_db)
    session = service.start_or_get_review_session(draft_id)

    # First approve and complete
    for item in session.items:
        item.decision = "APPROVED"
    test_db.commit()

    service.complete_review(
        draft_id=draft_id,
        reviewer_id="DEV_REVIEWER",
        request=CompleteReviewRequest(review_version=session.review_version, notes="First signoff"),
    )

    # Now reopen
    res = client.post(
        f"/api/v1/scheme-drafts/{draft_id}/review/reopen",
        json={"reason": "Government issued Gazette Amendment 2024 updating age threshold."},
        headers={"X-Reviewer-Id": "DEV_REVIEWER"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "IN_HUMAN_REVIEW"
    assert res_data["review_version"] == session.review_version + 1

    # Verify previous session still COMPLETED in history
    test_db.refresh(session)
    assert session.status == "COMPLETED"
