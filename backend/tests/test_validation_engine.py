import json
from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.scheme_draft import SchemeDraft
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
    ConflictRecord,
    ConflictValue,
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
from app.repositories.scheme_draft_repository import SchemeDraftRepository
from app.validation.schemas import ValidationRunStatus, ValidationSeverity
from app.validation.service import SchemeValidationService

client = TestClient(app)


@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_doc_and_draft(test_db):
    settings = get_settings()
    doc_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        document_code=f"DOC-VAL-{doc_id.hex[:6].upper()}",
        source_id=None,
        original_filename="val_test_doc.pdf",
        storage_path="storage/originals/val_test_doc.pdf",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        file_size_bytes=2048,
        page_count=10,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_VALIDATION",
    )
    test_db.add(doc)

    # Add chunk
    chunk = DocumentChunk(
        chunk_id_str=f"CHUNK-{doc_id}-001",
        document_id=doc_id,
        chunk_index=0,
        section_type="ELIGIBILITY",
        token_count=100,
        page_start=1,
        page_end=5,
        artifact_path=f"storage/chunks/{doc_id}/chunk_0.json",
    )
    test_db.add(chunk)

    # Create canonical JSON artifact directory
    draft_dir = settings.storage_path / "normalized" / str(doc_id) / str(draft_id)
    draft_dir.mkdir(parents=True, exist_ok=True)
    canonical_file = draft_dir / "canonical.json"

    rel_artifact_path = f"normalized/{doc_id}/{draft_id}/canonical.json"

    draft = SchemeDraft(
        id=draft_id,
        document_id=doc_id,
        internal_scheme_code=f"RJ-DRAFT-{draft_id.hex[:8].upper()}",
        detected_name="राजस्थान वृद्धावस्था पेंशन योजना",
        official_name_raw="राजस्थान वृद्धावस्था पेंशन योजना",
        normalized_name_for_matching="राजस्थान वृद्धावस्था पेंशन योजना",
        status="READY_FOR_VALIDATION",
        artifact_path=rel_artifact_path,
    )
    test_db.add(draft)
    test_db.commit()

    yield {
        "doc": doc,
        "draft": draft,
        "canonical_file": canonical_file,
        "chunk": chunk,
    }

    # Teardown
    try:
        test_db.delete(draft)
        test_db.delete(chunk)
        test_db.delete(doc)
        test_db.commit()
    except Exception:
        test_db.rollback()


def _build_valid_canonical_draft(doc_id: uuid.UUID, draft_id: uuid.UUID) -> CanonicalSchemeDraft:
    """Helper to construct a fully valid, passing CanonicalSchemeDraft."""
    ev1 = EvidenceRegistryItem(
        evidence_id="EVID-001",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[2],
        source_block_ids=["BLK-001"],
        text="आयु 60 वर्ष या अधिक होनी चाहिए।",
        raw_value="60 वर्ष",
    )
    ev2 = EvidenceRegistryItem(
        evidence_id="EVID-002",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[2],
        source_block_ids=["BLK-002"],
        text="वार्षिक पारिवारिक आय ₹2,00,000 से अधिक न हो।",
        raw_value="200000",
    )
    ev3 = EvidenceRegistryItem(
        evidence_id="EVID-003",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[3],
        source_block_ids=["BLK-003"],
        text="आवेदक राजस्थान का मूल निवासी होना चाहिए।",
        raw_value="राजस्थान",
    )
    ev4 = EvidenceRegistryItem(
        evidence_id="EVID-004",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[3],
        source_block_ids=["BLK-004"],
        text="प्रति माह ₹1,000 की पेंशन दी जाएगी।",
        raw_value="1000",
    )
    ev5 = EvidenceRegistryItem(
        evidence_id="EVID-005",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[4],
        source_block_ids=["BLK-005"],
        text="आवेदन हेतु आधार कार्ड अनिवार्य है।",
        raw_value="आधार कार्ड",
    )
    ev6 = EvidenceRegistryItem(
        evidence_id="EVID-006",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[4],
        source_block_ids=["BLK-006"],
        text="आवेदन https://sso.rajasthan.gov.in पर करें।",
        raw_value="https://sso.rajasthan.gov.in",
    )
    ev7 = EvidenceRegistryItem(
        evidence_id="EVID-007",
        document_id=str(doc_id),
        chunk_id=f"CHUNK-{doc_id}-001",
        page_numbers=[1],
        source_block_ids=["BLK-007"],
        text="प्रभावी तिथि 2026-04-01 से 2026-12-31 तक।",
        raw_value="2026-04-01",
    )

    cond_age = EligibilityCondition(
        condition_id="COND-001",
        field="age",
        operator=OperatorEnum.GTE,
        value=60,
        unit="years",
        raw_text="आयु 60 वर्ष या अधिक",
        evidence_refs=["EVID-001"],
    )
    cond_income = EligibilityCondition(
        condition_id="COND-002",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=200000,
        unit="INR",
        periodicity=PeriodicityEnum.ANNUAL,
        raw_text="पारिवारिक आय ₹2,00,000 से कम",
        evidence_refs=["EVID-002"],
    )
    cond_residency = EligibilityCondition(
        condition_id="COND-003",
        field="residency",
        operator=OperatorEnum.EQ,
        value="DOMICILE",
        raw_text="राजस्थान का मूल निवासी",
        evidence_refs=["EVID-003"],
    )

    root_rule = RuleGroup(
        type=LogicalGroupType.AND,
        children=[cond_age, cond_income, cond_residency],
    )

    eligibility = CanonicalEligibility(
        root_rule=root_rule,
        simple_fields={"min_age": 60, "max_age": 100, "family_income_max": 200000},
    )

    benefit = CanonicalBenefit(
        benefit_id="BEN-001",
        type=BenefitTypeEnum.PENSION,
        amount=1000.0,
        currency="INR",
        frequency=PeriodicityEnum.MONTHLY,
        description="प्रति माह ₹1,000 पेंशन",
        raw_text="प्रति माह ₹1,000 पेंशन",
        evidence_refs=["EVID-004"],
    )

    document_req = CanonicalDocument(
        document_id="DOC-001",
        document_type=DocumentTypeEnum.AADHAAR,
        name_raw="आधार कार्ड",
        mandatory=True,
        evidence_refs=["EVID-005"],
    )

    app_details = CanonicalApplication(
        channels=[ApplicationChannelEnum.ONLINE, ApplicationChannelEnum.EMITRA],
        portal_url="https://sso.rajasthan.gov.in",
        notes="e-Mitra or SSO portal",
        evidence_refs=["EVID-006"],
    )

    date1 = CanonicalImportantDate(
        event_name="effective_date",
        date_type="EXACT",
        normalized_date="2026-04-01",
        raw_date_text="1 अप्रैल 2026",
        evidence_refs=["EVID-007"],
    )
    date2 = CanonicalImportantDate(
        event_name="valid_until",
        date_type="EXACT",
        normalized_date="2026-12-31",
        raw_date_text="31 दिसंबर 2026",
        evidence_refs=["EVID-007"],
    )

    return CanonicalSchemeDraft(
        schema_version="1.0",
        normalizer_version="1.0",
        internal_scheme_code=f"RJ-DRAFT-{draft_id.hex[:8].upper()}",
        document_id=str(doc_id),
        status="READY_FOR_VALIDATION",
        scheme_identity=CanonicalIdentity(
            scheme_id=f"RJ-DRAFT-{draft_id.hex[:8].upper()}",
            name=SchemeNameDetail(raw="राजस्थान वृद्धावस्था पेंशन योजना", hi="राजस्थान वृद्धावस्था पेंशन योजना"),
            normalized_name_for_matching="राजस्थान वृद्धावस्था पेंशन योजना",
            jurisdiction="RAJASTHAN",
            scheme_origin=SchemeOriginEnum.RAJASTHAN_STATE,
        ),
        scope=CanonicalScope(
            state="Rajasthan",
            districts=["Udaipur", "उदयपुर", "Jaipur"],
            rural_urban="BOTH",
        ),
        eligibility=eligibility,
        exclusions=[],
        benefits=[benefit],
        required_documents=[document_req],
        application=app_details,
        important_dates=[date1, date2],
        evidence_registry={
            "EVID-001": ev1,
            "EVID-002": ev2,
            "EVID-003": ev3,
            "EVID-004": ev4,
            "EVID-005": ev5,
            "EVID-006": ev6,
            "EVID-007": ev7,
        },
    )


# ---------------------------------------------------------------------------
# Test 1: Full Valid Draft Passes
# ---------------------------------------------------------------------------
def test_complete_valid_draft_passes(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id)

    assert report.status == ValidationRunStatus.VALIDATION_PASSED
    assert report.summary.blockers == 0
    assert report.summary.errors == 0
    assert report.summary.total_issues == 0

    # Verify SchemeDraft updated in DB
    test_db.refresh(test_doc_and_draft["draft"])
    assert test_doc_and_draft["draft"].status == "VALIDATION_PASSED"


# ---------------------------------------------------------------------------
# Test 2: Schema Failure (Malformed / Missing Fields)
# ---------------------------------------------------------------------------
def test_schema_invalid_malformed_json(test_db, test_doc_and_draft):
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    # Write malformed JSON
    canonical_file.write_text("{ not valid json }", encoding="utf-8")

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert report.status == ValidationRunStatus.VALIDATION_FAILED
    assert report.summary.blockers > 0
    issue_codes = [i.rule_code for i in report.issues]
    assert "SCHEMA_INVALID" in issue_codes


def test_required_field_missing(test_db, test_doc_and_draft):
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    # Write json missing scheme_identity
    canonical_file.write_text(json.dumps({"document_id": str(uuid.uuid4())}), encoding="utf-8")

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert report.status == ValidationRunStatus.VALIDATION_FAILED
    issue_codes = [i.rule_code for i in report.issues]
    assert "REQUIRED_FIELD_MISSING" in issue_codes


# ---------------------------------------------------------------------------
# Test 3: Missing Evidence Reference
# ---------------------------------------------------------------------------
def test_missing_evidence_reference(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Strip evidence_refs from age condition
    draft_obj.eligibility.root_rule.children[0].evidence_refs = []

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert report.status == ValidationRunStatus.VALIDATION_REVIEW_REQUIRED
    issue_codes = [i.rule_code for i in report.issues]
    assert "EVIDENCE_REF_MISSING" in issue_codes


# ---------------------------------------------------------------------------
# Test 4: Unknown Evidence Reference in Registry
# ---------------------------------------------------------------------------
def test_invalid_evidence_id_in_registry(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Reference non-existent evidence
    draft_obj.eligibility.root_rule.children[0].evidence_refs = ["EVID-999"]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert report.status == ValidationRunStatus.VALIDATION_FAILED
    assert report.summary.blockers > 0
    issue_codes = [i.rule_code for i in report.issues]
    assert "EVIDENCE_REGISTRY_MISSING" in issue_codes


# ---------------------------------------------------------------------------
# Test 5: Page Number Outside Bounds
# ---------------------------------------------------------------------------
def test_evidence_page_out_of_bounds(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Document has 10 pages, evidence specifies page 25
    draft_obj.evidence_registry["EVID-001"].page_numbers = [25]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    issue_codes = [i.rule_code for i in report.issues]
    assert "EVIDENCE_PAGE_INVALID" in issue_codes


# ---------------------------------------------------------------------------
# Test 6: Age Checks (Negative, Excessive, Range Bounds)
# ---------------------------------------------------------------------------
def test_age_checks(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    # Negative age
    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.eligibility.root_rule.children[0].value = -15
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)
    assert "AGE_NEGATIVE" in [i.rule_code for i in report.issues]

    # Suspicious age (> 125)
    draft_obj.eligibility.root_rule.children[0].value = 150
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    report = service.validate_draft(draft_id, force=True)
    assert "AGE_SUSPICIOUS" in [i.rule_code for i in report.issues]


def test_age_range_invalid(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.eligibility.simple_fields["min_age"] = 60
    draft_obj.eligibility.simple_fields["max_age"] = 40

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)
    assert "AGE_RANGE_INVALID" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 7: Income Checks (Negative, Extreme, Period Mismatch)
# ---------------------------------------------------------------------------
def test_income_checks(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    # Negative income
    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.eligibility.root_rule.children[1].value = -50000
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)
    assert "INCOME_NEGATIVE" in [i.rule_code for i in report.issues]

    # Extreme income (> 10 crore)
    draft_obj.eligibility.root_rule.children[1].value = 200000000
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    report = service.validate_draft(draft_id, force=True)
    assert "INCOME_EXTREME_VALUE" in [i.rule_code for i in report.issues]

    # Periodicity mismatch
    draft_obj.eligibility.root_rule.children[1].field = "annual_income"
    draft_obj.eligibility.root_rule.children[1].periodicity = PeriodicityEnum.MONTHLY
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    report = service.validate_draft(draft_id, force=True)
    assert "INCOME_PERIOD_MISMATCH" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 8: Percentage Out of Range
# ---------------------------------------------------------------------------
def test_percentage_out_of_range(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    p_cond = EligibilityCondition(
        condition_id="COND-099",
        field="disability_percentage",
        operator=OperatorEnum.GTE,
        value=140,
        unit="PERCENT",
        raw_text="दिव्यांगता 140 प्रतिशत",
        evidence_refs=["EVID-001"],
    )
    draft_obj.eligibility.root_rule.children.append(p_cond)

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)
    assert "PERCENTAGE_OUT_OF_RANGE" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 9: Dates (Invalid Calendar Date, Inverted Date Range)
# ---------------------------------------------------------------------------
def test_date_validations(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    # Non-existent calendar date
    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.important_dates[0].normalized_date = "2026-02-30"

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)
    assert "DATE_INVALID" in [i.rule_code for i in report.issues]

    # Inverted date range (start > end)
    draft_obj.important_dates[0].normalized_date = "2027-01-01"  # start
    draft_obj.important_dates[1].normalized_date = "2026-01-01"  # end
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    report = service.validate_draft(draft_id, force=True)
    assert "DATE_RANGE_INVALID" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 10: Rajasthan Geography & Districts
# ---------------------------------------------------------------------------
def test_district_and_state_validation(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.scope.districts = ["Udaipur", "उदयपुर", "RandomFakeDistrict"]
    draft_obj.scope.state = "Gujarat"

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    issue_codes = [i.rule_code for i in report.issues]
    assert "DISTRICT_UNKNOWN" in issue_codes
    assert "STATE_CONFLICT" in issue_codes


# ---------------------------------------------------------------------------
# Test 11: Contradictory Rules vs Compatible Rules
# ---------------------------------------------------------------------------
def test_contradictory_conditions_in_and_group(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Add age < 40 while age >= 60 exists in same AND group
    contradicting_cond = EligibilityCondition(
        condition_id="COND-004",
        field="age",
        operator=OperatorEnum.LT,
        value=40,
        raw_text="आयु 40 वर्ष से कम",
        evidence_refs=["EVID-001"],
    )
    draft_obj.eligibility.root_rule.children.append(contradicting_cond)

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert "CONTRADICTORY_RULES" in [i.rule_code for i in report.issues]


def test_or_branch_not_contradictory(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # BPL == True OR income <= 200000 should NOT be contradictory
    bpl_cond = EligibilityCondition(
        condition_id="COND-BPL",
        field="is_bpl",
        operator=OperatorEnum.EQ,
        value=True,
        raw_text="बीपीएल परिवार",
        evidence_refs=["EVID-001"],
    )
    income_cond = EligibilityCondition(
        condition_id="COND-INC",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=200000,
        raw_text="आय 2 लाख",
        evidence_refs=["EVID-002"],
    )
    or_group = RuleGroup(type=LogicalGroupType.OR, children=[bpl_cond, income_cond])
    draft_obj.eligibility.root_rule.children = [or_group]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert "CONTRADICTORY_RULES" not in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 12: Rule Group Structure (Empty Group, NOT Child Count)
# ---------------------------------------------------------------------------
def test_rule_group_structure_errors(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Empty AND group
    empty_and = RuleGroup(type=LogicalGroupType.AND, children=[])
    # NOT group with 2 children
    c1 = EligibilityCondition(condition_id="C1", field="age", operator=OperatorEnum.GT, value=10, raw_text="t", evidence_refs=["EVID-001"])
    c2 = EligibilityCondition(condition_id="C2", field="age", operator=OperatorEnum.GT, value=20, raw_text="t", evidence_refs=["EVID-001"])
    bad_not = RuleGroup(type=LogicalGroupType.NOT, children=[c1, c2])

    draft_obj.eligibility.root_rule.children = [empty_and, bad_not]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    issue_codes = [i.rule_code for i in report.issues]
    assert "RULE_GROUP_EMPTY" in issue_codes
    assert "RULE_NOT_INVALID" in issue_codes


# ---------------------------------------------------------------------------
# Test 13: Operator Compatibility & Missing Value
# ---------------------------------------------------------------------------
def test_operator_compatibility_and_null_value(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # gender GTE FEMALE
    gender_cond = EligibilityCondition(
        condition_id="COND-GEN",
        field="gender",
        operator=OperatorEnum.GTE,
        value="FEMALE",
        raw_text="महिला",
        evidence_refs=["EVID-001"],
    )
    # Operator requiring value has value=None
    null_val_cond = EligibilityCondition(
        condition_id="COND-NUL",
        field="age",
        operator=OperatorEnum.GTE,
        value=None,
        raw_text="आयु",
        evidence_refs=["EVID-001"],
    )
    draft_obj.eligibility.root_rule.children = [gender_cond, null_val_cond]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    issue_codes = [i.rule_code for i in report.issues]
    assert "OPERATOR_INCOMPATIBLE" in issue_codes
    assert "RULE_VALUE_MISSING" in issue_codes


# ---------------------------------------------------------------------------
# Test 14: Custom Unsupported Field Handling
# ---------------------------------------------------------------------------
def test_custom_condition_not_fatal(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    custom_cond = EligibilityCondition(
        condition_id="COND-CUST",
        field="CUSTOM",
        custom_field_name="registered labour days",
        operator=OperatorEnum.GTE,
        value=100,
        raw_text="न्यूनतम 100 दिवस पंजीकृत श्रमिक",
        evidence_refs=["EVID-001"],
    )
    draft_obj.eligibility.root_rule.children.append(custom_cond)

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    # Should raise CUSTOM_FIELD_REQUIRED (INFO) and UNSUPPORTED (WARNING), not BLOCKER
    issue_codes = [i.rule_code for i in report.issues]
    assert "CUSTOM_FIELD_REQUIRED" in issue_codes
    assert "UNSUPPORTED_FOR_AUTOMATIC_ELIGIBILITY" in issue_codes
    assert report.summary.blockers == 0


# ---------------------------------------------------------------------------
# Test 15: Benefits (Negative Amount)
# ---------------------------------------------------------------------------
def test_benefits_negative_amount(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.benefits[0].amount = -1000.0

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert "BENEFIT_NEGATIVE_AMOUNT" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 16: Application URL Safety
# ---------------------------------------------------------------------------
def test_application_url_safety(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    draft_obj.application.portal_url = "javascript:alert(document.cookie)"

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert report.status == ValidationRunStatus.VALIDATION_FAILED
    assert "APPLICATION_URL_UNSAFE" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 17: OCR Risk Propagation for Numeric Facts
# ---------------------------------------------------------------------------
def test_ocr_risk_propagation(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    # Mark EVID-001 as low-confidence OCR extraction method
    draft_obj.evidence_registry["EVID-001"].extraction_method = "PADDLEOCR"

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    # EVID-001 supports age (sensitive numeric)
    assert "LOW_CONFIDENCE_NUMERIC_OCR" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 18: Unresolved Critical Conflict
# ---------------------------------------------------------------------------
def test_unresolved_critical_conflict(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    conf = ConflictRecord(
        conflict_id="CONF-001",
        field="family_income",
        values=[
            ConflictValue(value=200000, raw_text="आय ₹2,00,000", evidence_refs=["EVID-002"]),
            ConflictValue(value=300000, raw_text="आय ₹3,00,000", evidence_refs=["EVID-002"]),
        ],
        status="REVIEW_REQUIRED",
    )
    draft_obj.conflicts = [conf]

    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    assert "UNRESOLVED_CRITICAL_CONFLICT" in [i.rule_code for i in report.issues]


# ---------------------------------------------------------------------------
# Test 19: Provenance Chain
# ---------------------------------------------------------------------------
def test_provenance_chain_resolution(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report = service.validate_draft(draft_id, force=True)

    # Confirm field -> evidence -> chunk -> doc resolves without lineage errors
    issue_codes = [i.rule_code for i in report.issues]
    assert "CHUNK_INVALID" not in issue_codes
    assert "DOCUMENT_MISMATCH" not in issue_codes
    assert "EVIDENCE_REGISTRY_MISSING" not in issue_codes


# ---------------------------------------------------------------------------
# Test 20: Stale Validation Detection
# ---------------------------------------------------------------------------
def test_stale_validation_detection(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report1 = service.validate_draft(draft_id)
    assert report1.status == ValidationRunStatus.VALIDATION_PASSED

    # Modify canonical artifact (change benefit amount)
    draft_obj.benefits[0].amount = 1500.0
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    # Re-validate
    report2 = service.validate_draft(draft_id)
    assert report2.status == ValidationRunStatus.VALIDATION_PASSED

    # Verify first run was marked STALE in DB
    runs = test_db.query(ValidationRun).filter(ValidationRun.scheme_draft_id == draft_id).order_by(ValidationRun.created_at.asc()).all()
    assert len(runs) >= 2
    assert runs[0].status == "STALE"
    assert runs[-1].status == "VALIDATION_PASSED"


# ---------------------------------------------------------------------------
# Test 21: Worker Idempotency
# ---------------------------------------------------------------------------
def test_worker_idempotency_reuses_run(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    service = SchemeValidationService(test_db)
    report1 = service.validate_draft(draft_id)

    # Run again without force
    report2 = service.validate_draft(draft_id, force=False)
    assert report1.canonical_artifact_hash == report2.canonical_artifact_hash

    # Count runs in database
    run_count = test_db.query(ValidationRun).filter(ValidationRun.scheme_draft_id == draft_id).count()
    assert run_count == 1  # Reused cached run!


# ---------------------------------------------------------------------------
# Test 22: REST API Endpoints
# ---------------------------------------------------------------------------
def test_validation_rest_api(test_db, test_doc_and_draft):
    doc_id = test_doc_and_draft["doc"].id
    draft_id = test_doc_and_draft["draft"].id
    canonical_file = test_doc_and_draft["canonical_file"]

    draft_obj = _build_valid_canonical_draft(doc_id, draft_id)
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(draft_obj.model_dump(), f, ensure_ascii=False)

    # 1. POST /api/v1/scheme-drafts/{draft_id}/validate
    res_validate = client.post(f"/api/v1/scheme-drafts/{draft_id}/validate")
    assert res_validate.status_code == 200
    data = res_validate.json()
    assert data["status"] == "VALIDATION_PASSED"
    assert "canonical_artifact_hash" in data

    # 2. GET /api/v1/scheme-drafts/{draft_id}/validation
    res_run = client.get(f"/api/v1/scheme-drafts/{draft_id}/validation")
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["status"] == "VALIDATION_PASSED"
    assert run_data["scheme_draft_id"] == str(draft_id)

    # 3. GET /api/v1/scheme-drafts/{draft_id}/validation/issues
    res_issues = client.get(f"/api/v1/scheme-drafts/{draft_id}/validation/issues")
    assert res_issues.status_code == 200
    assert isinstance(res_issues.json(), list)

    # 4. GET /api/v1/validation-runs/{run_id}
    run_id = run_data["id"]
    res_single_run = client.get(f"/api/v1/validation-runs/{run_id}")
    assert res_single_run.status_code == 200
    assert res_single_run.json()["id"] == run_id
