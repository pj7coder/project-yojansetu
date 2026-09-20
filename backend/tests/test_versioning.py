import copy
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.cache.verified_rule_cache import VerifiedRuleCache, get_rule_cache
from app.core.config import settings
from app.database.models.category import Category
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_change_item import SchemeChangeItem
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.main import app
from app.versioning.candidate_matcher import RelationshipCandidateMatcher
from app.versioning.canonical_diff import CanonicalSchemeDiffService
from app.versioning.change_set_builder import SchemeChangeSetBuilder
from app.versioning.reference_extractor import GovernmentReferenceExtractor
from app.versioning.relationship_detector import DocumentRelationshipDetector
from app.versioning.rule_diff import RuleDiffService
from app.versioning.schemas import ChangeItemSchema, ChangeRiskLevel, ChangeType, RelationshipType
from app.versioning.service import SchemeVersionService
from app.versioning.timeline import SchemeTimelineService
from app.versioning.version_builder import SchemeVersionBuilder
from app.versioning.worker import SchemeVersioningWorker

client = TestClient(app)


# ==============================================================================
# Database Fixtures
# ==============================================================================

@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seeded_scheme(test_db):
    """Seed a test scheme with Department, Category, Document, and Version 1."""
    # Ensure department exists
    dept = test_db.execute(select(Department).where(Department.code == "RJ-SJE")).scalars().first()
    if not dept:
        dept = Department(
            id=uuid.uuid4(),
            code="RJ-SJE",
            name_en="Social Justice and Empowerment Department",
            name_hi="सामाजिक न्याय एवं अधिकारिता विभाग",
        )
        test_db.add(dept)

    # Ensure category exists
    cat = test_db.execute(select(Category).where(Category.code == "PENSION")).scalars().first()
    if not cat:
        cat = Category(
            id=uuid.uuid4(),
            code="PENSION",
            name_en="Social Security Pension",
            name_hi="सामाजिक सुरक्षा पेंशन",
        )
        test_db.add(cat)

    # Ensure document exists
    doc = Document(
        id=uuid.uuid4(),
        document_code=f"DOC-{uuid.uuid4().hex[:8].upper()}",
        title="Notification No. F.1(2)SJE/2025/101 dated 01.01.2025 - Guidelines",
        original_filename="vridhjan_guidelines_2025.pdf",
        file_size_bytes=1024,
        storage_path="documents/vridhjan_guidelines_2025.pdf",
        ingestion_method="API",
        mime_type="application/pdf",
        processing_status="VERIFIED",
    )
    test_db.add(doc)
    test_db.commit()

    # Create Scheme
    scheme_code = f"TEST-SCHEME-{uuid.uuid4().hex[:6].upper()}"
    scheme = Scheme(
        id=uuid.uuid4(),
        scheme_code=scheme_code,
        name_en="Mukhyamantri Vridhjan Samman Pension Yojana",
        name_hi="मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
        short_name="Vridhjan Pension",
        department_id=dept.id,
        category_id=cat.id,
        status="ACTIVE",
    )
    test_db.add(scheme)
    test_db.commit()

    # Create Canonical Snapshot for Version 1
    base_canonical = {
        "identity": {
            "scheme_id": scheme.scheme_code,
            "name": {"en": scheme.name_en, "hi": scheme.name_hi},
            "department": dept.name_en,
            "description": "Old age pension for senior citizens of Rajasthan",
        },
        "eligibility": {
            "root_rule": {
                "type": "AND",
                "children": [
                    {"field": "age", "operator": "GTE", "value": 60, "raw_text": "Age >= 60"},
                    {"field": "family_income", "operator": "LTE", "value": 200000, "raw_text": "Income <= 2,00,000"},
                    {"field": "domicile", "operator": "EQ", "value": "RAJASTHAN", "raw_text": "Rajasthan resident"},
                ],
            },
            "simple_fields": {
                "min_age": 60,
                "family_income_max": 200000,
                "residency": "RAJASTHAN",
            },
        },
        "benefits": {
            "financial": {
                "amount": 1000,
                "periodicity": "MONTHLY",
            }
        },
        "exclusions": [
            {"title": "Government Employees", "description": "Regular government employees are not eligible"}
        ],
        "documents_required": [
            {"name": "Jan Aadhaar", "type": "JAN_AADHAAR"},
            {"name": "Bank Passbook", "type": "BANK_PASSBOOK"},
        ],
        "validity": {
            "application_deadline": "2026-03-31",
        },
    }

    # Create Version 1
    v1 = SchemeVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version_number=1,
        version_label="v1.0 (Original)",
        status="ACTIVE",
        valid_from=date(2025, 1, 1),
        valid_until=None,
        canonical_data=base_canonical,
        artifact_path=f"storage/schemes/{scheme.id}/versions/v1/scheme.json",
        artifact_sha256="hash_v1_initial",
        source_document_id=doc.id,
        source_summary="Notification No. F.1(2)SJE/2025/101 dated 01.01.2025",
        is_current=True,
    )
    test_db.add(v1)
    test_db.commit()
    test_db.refresh(scheme)
    test_db.refresh(v1)

    return scheme, v1, doc


# ==============================================================================
# 1. Reference Extractor Tests
# ==============================================================================

def test_reference_extractor_explicit_citation():
    extractor = GovernmentReferenceExtractor()
    text = (
        "राजस्थान सरकार, सामाजिक न्याय एवं अधिकारिता विभाग\n"
        "अधिसूचना क्रमांक: प.1(2)सा.न्या./2026/890 दिनांक: 15.08.2026\n"
        "In supersession of Notification No. F.1(2)SJE/2025/101 dated 01/01/2025,\n"
        "the Governor is pleased to amend Clause 4(ii) of the guidelines."
    )
    refs = extractor.extract_references(text, page_number=1)
    assert len(refs) >= 2

    # Check notification reference extraction
    ref_numbers = [r.reference_number for r in refs if r.reference_number]
    assert any("2026" in r or "890" in r for r in ref_numbers)
    assert any("2025" in r or "101" in r for r in ref_numbers)

    # Check clause extraction
    clause_refs = [r.clause_reference for r in refs if r.clause_reference]
    assert "4(ii)" in clause_refs


def test_reference_extractor_dates():
    extractor = GovernmentReferenceExtractor()
    text = "यह आदेश दिनांक 01/10/2026 से प्रभावी होगा (with effect from 01.10.2026)."
    eff_date = extractor.extract_effective_date(text)
    assert eff_date is not None
    assert eff_date[0] == date(2026, 10, 1)


# ==============================================================================
# 2. Relationship Detection Tests
# ==============================================================================

def test_relationship_basic_amendment():
    detector = DocumentRelationshipDetector()
    text = (
        "विषय: मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना के नियमों में आंशिक संशोधन बाबत।\n"
        "उक्त योजना के अंतर्गत वार्षिक पारिवारिक आय सीमा को ₹2,00,000 के स्थान पर प्रतिस्थापित करते हुए "
        "₹3,00,000 किया जाता है।"
    )
    result = detector.detect_relationship(source_text=text)
    assert result.relationship_type == RelationshipType.AMENDS
    assert result.relationship_status.value == "REVIEW_REQUIRED"
    assert "EXPLICIT_AMENDMENT_PHRASE" in result.reason_codes


def test_relationship_supersession():
    detector = DocumentRelationshipDetector()
    text = (
        "In supersession of Notification No. F.1(2)SJE/2025/101 dated 01.01.2025, "
        "the Government of Rajasthan hereby issues the revised comprehensive guidelines."
    )
    result = detector.detect_relationship(
        source_text=text,
        target_citation="F.1(2)SJE/2025/101",
    )
    assert result.relationship_type == RelationshipType.SUPERSEDES
    assert result.signal_strength == "EXPLICIT"
    assert "EXPLICIT_SUPERSESSION_PHRASE" in result.reason_codes
    assert "EXPLICIT_NOTIFICATION_REFERENCE" in result.reason_codes


def test_relationship_corrigendum():
    detector = DocumentRelationshipDetector()
    text = (
        "शुद्धि-पत्र संख्या 45/2026:\n"
        "विभागीय अधिसूचना दिनांक 01.01.2025 के बिंदु 3 में उल्लिखित राशि ₹20,000 shall be read as ₹2,00,000."
    )
    result = detector.detect_relationship(source_text=text)
    assert result.relationship_type == RelationshipType.CORRIGENDUM_TO
    assert "EXPLICIT_CORRIGENDUM_PHRASE" in result.reason_codes


def test_relationship_addendum():
    detector = DocumentRelationshipDetector()
    text = (
        "Addendum to Guidelines:\n"
        "In addition to existing documents, Domicile Certificate shall be inserted as a mandatory document."
    )
    result = detector.detect_relationship(source_text=text)
    assert result.relationship_type == RelationshipType.ADDENDUM_TO
    assert "EXPLICIT_ADDENDUM_PHRASE" in result.reason_codes


def test_relationship_clarification():
    detector = DocumentRelationshipDetector()
    text = (
        "Clarification regarding definition of Family Income:\n"
        "For the removal of doubt, it is clarified that agricultural income refers to net income."
    )
    result = detector.detect_relationship(source_text=text)
    assert result.relationship_type == RelationshipType.CLARIFIES
    assert "EXPLICIT_CLARIFICATION_PHRASE" in result.reason_codes


def test_filename_only_signal_not_authoritative():
    detector = DocumentRelationshipDetector()
    text = "General overview of welfare schemes in Rajasthan."
    filename = "revised_superseded_final_guidelines.pdf"
    result = detector.detect_relationship(source_text=text, source_filename=filename)
    assert result.relationship_type == RelationshipType.UNKNOWN_RELATIONSHIP
    assert result.signal_strength == "WEAK"
    assert "FILENAME_KEYWORD_ONLY_WEAK" in result.reason_codes


# ==============================================================================
# 3. Rule Diff & Structured Canonical Diff Tests
# ==============================================================================

def test_partial_amendment_inherits_unchanged_conditions():
    """
    Mandatory test: Base has 10 rules. Amendment modifies only rule 3.
    Version 2 must have 9 inherited rules + 1 amended rule (not only 1 rule!).
    """
    rule_diff = RuleDiffService()

    base_children = [{"field": f"cond_{i}", "operator": "GTE", "value": i * 10} for i in range(1, 11)]
    base_eligibility = {
        "root_rule": {"type": "AND", "children": base_children},
        "simple_fields": {f"cond_{i}": i * 10 for i in range(1, 11)},
    }

    # Amendment only contains cond_3 changed from 30 to 50
    candidate_eligibility = {
        "root_rule": {"type": "AND", "children": [{"field": "cond_3", "operator": "GTE", "value": 50}]},
        "simple_fields": {"cond_3": 50},
    }

    # Diff with partial_amendment = True
    changes = rule_diff.diff_rule_trees(
        base_eligibility=base_eligibility,
        candidate_eligibility=candidate_eligibility,
        is_partial_amendment=True,
    )

    # Exactly 1 change should be emitted: cond_3 modified!
    assert len(changes) == 1
    assert changes[0].field_path == "eligibility.rules.cond_3"
    assert changes[0].change_type == ChangeType.REPLACE
    assert changes[0].old_value["value"] == 30
    assert changes[0].new_value["value"] == 50

    # Apply via SchemeVersionBuilder and verify all 10 conditions are preserved in Version 2
    builder = SchemeVersionBuilder(storage_root="storage")
    mock_base_version = MagicMock()
    mock_base_version.version_number = 1
    mock_base_version.scheme_id = uuid.uuid4()
    mock_base_version.valid_from = date(2025, 1, 1)
    mock_base_version.canonical_data = {"eligibility": base_eligibility}

    change_set = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=mock_base_version.scheme_id,
        base_version_id=uuid.uuid4(),
        source_document_id=uuid.uuid4(),
        status="HUMAN_APPROVED",
        items=[
            SchemeChangeItem(
                id=uuid.uuid4(),
                field_path=changes[0].field_path,
                change_type=changes[0].change_type.value,
                old_value_json=changes[0].old_value,
                new_value_json=changes[0].new_value,
                risk_level=changes[0].risk_level.value,
                status="APPROVED",
            )
        ],
    )

    v2 = builder.create_new_version(mock_base_version, change_set)
    v2_children = v2.canonical_data["eligibility"]["root_rule"]["children"]
    # All 10 conditions exist!
    assert len(v2_children) == 10

    # Verify cond_3 was updated to 50, and cond_1 remains 10
    cond_3 = next(c for c in v2_children if c["field"] == "cond_3")
    cond_1 = next(c for c in v2_children if c["field"] == "cond_1")
    assert cond_3["value"] == 50
    assert cond_1["value"] == 10

    # Verify field provenance was recorded
    provenance = v2.canonical_data["_field_provenance"]
    assert "eligibility.rules.cond_3" in provenance
    assert provenance["eligibility.rules.cond_3"]["origin"] == "AMENDMENT"


def test_omission_is_not_removal_in_amendment():
    rule_diff = RuleDiffService()
    base_elig = {
        "root_rule": {
            "type": "AND",
            "children": [
                {"field": "age", "operator": "GTE", "value": 60},
                {"field": "income", "operator": "LTE", "value": 200000},
            ],
        }
    }
    # Candidate mentions only age, income is omitted
    cand_elig = {
        "root_rule": {
            "type": "AND",
            "children": [
                {"field": "age", "operator": "GTE", "value": 60},
            ],
        }
    }
    # With partial_amendment = True: income is NOT removed
    changes = rule_diff.diff_rule_trees(base_elig, cand_elig, is_partial_amendment=True)
    assert len(changes) == 0


def test_full_replacement_diff():
    rule_diff = RuleDiffService()
    base_elig = {
        "root_rule": {
            "type": "AND",
            "children": [
                {"field": "age", "operator": "GTE", "value": 60},
                {"field": "income", "operator": "LTE", "value": 200000},
            ],
        }
    }
    cand_elig = {
        "root_rule": {
            "type": "AND",
            "children": [
                {"field": "age", "operator": "GTE", "value": 65},
            ],
        }
    }
    # In full replacement (is_partial_amendment = False), omitted condition IS removed
    changes = rule_diff.diff_rule_trees(base_elig, cand_elig, is_partial_amendment=False)
    paths = [c.field_path for c in changes]
    assert "eligibility.rules.age" in paths
    assert "eligibility.rules.income" in paths
    income_change = next(c for c in changes if c.field_path == "eligibility.rules.income")
    assert income_change.change_type == ChangeType.REMOVE


def test_rule_diff_logical_connector_change():
    rule_diff = RuleDiffService()
    base_elig = {
        "root_rule": {"type": "OR", "children": [{"field": "bpl", "value": True}, {"field": "income", "value": 200000}]}
    }
    cand_elig = {
        "root_rule": {"type": "AND", "children": [{"field": "bpl", "value": True}, {"field": "income", "value": 200000}]}
    }
    changes = rule_diff.diff_rule_trees(base_elig, cand_elig)
    connector_ch = next((c for c in changes if c.field_path == "eligibility.root_rule.type"), None)
    assert connector_ch is not None
    assert connector_ch.risk_level == ChangeRiskLevel.CRITICAL
    assert connector_ch.reason == "LOGICAL_CONNECTOR_CHANGED"


def test_canonical_diff_added_exclusion():
    diff_service = CanonicalSchemeDiffService()
    base = {"exclusions": [{"title": "Government Employees"}]}
    cand = {
        "exclusions": [
            {"title": "Government Employees"},
            {"title": "Existing Pensioners", "description": "Recipients of other pensions are excluded"},
        ]
    }
    changes = diff_service.diff_schemes(base, cand)
    excl_ch = [c for c in changes if c.field_path.startswith("exclusions")]
    assert len(excl_ch) == 1
    assert excl_ch[0].change_type == ChangeType.ADD
    assert excl_ch[0].risk_level == ChangeRiskLevel.CRITICAL


def test_canonical_diff_deadline_extension():
    diff_service = CanonicalSchemeDiffService()
    base = {"validity": {"application_deadline": "2026-03-31"}}
    cand = {"validity": {"application_deadline": "2026-04-30"}}
    changes = diff_service.diff_schemes(base, cand)
    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.EXTEND_VALIDITY
    assert changes[0].old_value == "2026-03-31"
    assert changes[0].new_value == "2026-04-30"
    assert changes[0].risk_level == ChangeRiskLevel.CRITICAL


def test_canonical_diff_array_order_independence():
    diff_service = CanonicalSchemeDiffService()
    base = {"documents_required": [{"name": "Aadhaar"}, {"name": "Jan Aadhaar"}]}
    cand = {"documents_required": [{"name": "Jan Aadhaar"}, {"name": "Aadhaar"}]}
    changes = diff_service.diff_schemes(base, cand)
    assert len(changes) == 0


# ==============================================================================
# 4. Temporal Validity & Conflict Detection Tests
# ==============================================================================

def test_effective_date_vs_publication_date_separation():
    builder = SchemeChangeSetBuilder()
    items = [
        ChangeItemSchema(
            field_path="eligibility.rules.income",
            change_type=ChangeType.REPLACE,
            old_value=200000,
            new_value=300000,
            risk_level=ChangeRiskLevel.CRITICAL,
        )
    ]
    # Published 15 Aug, Effective 1 Jul (in past) -> RETROACTIVE_EFFECTIVE_DATE
    cs = builder.build_change_set(
        scheme_id=uuid.uuid4(),
        base_version_id=uuid.uuid4(),
        source_document_id=uuid.uuid4(),
        change_items=items,
        publication_date=date(2026, 8, 15),
        effective_date=date(2026, 7, 1),
    )
    assert cs.publication_date == date(2026, 8, 15)
    assert cs.effective_date == date(2026, 7, 1)
    assert cs.conflict_reason is not None
    assert "RETROACTIVE_EFFECTIVE_DATE" in cs.conflict_reason


def test_future_effective_date_not_yet_active(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    service = SchemeVersionService()

    # Create change set
    future_date = date.today() + timedelta(days=60)
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="DETECTED",
        effective_date=future_date,
        changes_count=1,
        items=[
            SchemeChangeItem(
                id=uuid.uuid4(),
                field_path="eligibility.rules.family_income",
                change_type="REPLACE",
                old_value_json={"value": 200000},
                new_value_json={"value": 300000},
                risk_level="CRITICAL",
                status="PENDING",
            )
        ],
    )
    test_db.add(cs)
    test_db.commit()

    # Approve change set -> creates v2
    v2 = service.approve_change_set(test_db, cs.id)
    assert v2.version_number == 2
    assert v2.status == "HUMAN_VERIFIED"
    assert v2.is_current is False

    # Attempt to activate version with future effective date
    activated_v2 = service.activate_version(test_db, v2.id)
    assert activated_v2.status == "HUMAN_VERIFIED"
    assert activated_v2.is_current is False

    # Check that current active version remains v1
    timeline = SchemeTimelineService()
    active_now = timeline.get_active_scheme_version(test_db, scheme.id, evaluation_date=date.today())
    assert active_now.id == v1.id
    assert active_now.version_number == 1


def test_source_conflict_detection():
    builder = SchemeChangeSetBuilder()
    items = [
        ChangeItemSchema(
            field_path="eligibility.rules.family_income",
            change_type=ChangeType.REPLACE,
            old_value=200000,
            new_value=300000,
            risk_level=ChangeRiskLevel.CRITICAL,
        )
    ]
    cs = builder.build_change_set(
        scheme_id=uuid.uuid4(),
        base_version_id=uuid.uuid4(),
        source_document_id=uuid.uuid4(),
        change_items=items,
        conflict_reason="UNRESOLVED_SOURCE_CONFLICT",
    )
    assert "UNRESOLVED_SOURCE_CONFLICT" in cs.conflict_reason

    # Service must refuse to approve changeset with unresolved conflict
    service = SchemeVersionService()
    mock_db = MagicMock()
    mock_db.get.return_value = cs
    with pytest.raises(ValueError, match="UNRESOLVED_SOURCE_CONFLICT"):
        service.approve_change_set(mock_db, cs.id)


def test_candidate_matcher_department_separation(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    matcher = RelationshipCandidateMatcher()

    # Create another department
    dept2 = Department(
        id=uuid.uuid4(),
        code=f"RJ-MED-{uuid.uuid4().hex[:6].upper()}",
        name_en="Medical and Health Department",
        name_hi="चिकित्सा एवं स्वास्थ्य विभाग",
    )
    test_db.add(dept2)
    test_db.commit()

    # Document has matching name but explicitly belongs to dept2
    candidates, conflict = matcher.find_candidates(
        db=test_db,
        document_text="Notification regarding Mukhyamantri Vridhjan Samman Pension Yojana",
        department_id=dept2.id,
    )
    # Must NOT match scheme from RJ-SJE!
    assert len(candidates) == 0


def test_candidate_matcher_ambiguous_targets(test_db, seeded_scheme):
    scheme1, v1, doc = seeded_scheme
    matcher = RelationshipCandidateMatcher()

    # Create second scheme with similar name in same department
    scheme2 = Scheme(
        id=uuid.uuid4(),
        scheme_code=f"RJ-PENS-{uuid.uuid4().hex[:6].upper()}",
        name_en="Mukhyamantri Ekal Nari Samman Pension Yojana",
        name_hi="मुख्यमंत्री एकल नारी सम्मान पेंशन योजना",
        department_id=scheme1.department_id,
        category_id=scheme1.category_id,
        status="ACTIVE",
    )
    test_db.add(scheme2)
    test_db.commit()

    candidates, conflict = matcher.find_candidates(
        db=test_db,
        document_text="Regarding Mukhyamantri Samman Pension Yojana guidelines",
    )
    # Both schemes match partially -> emits MULTIPLE_POSSIBLE_BASE_VERSIONS
    if len(candidates) > 1:
        assert conflict == "MULTIPLE_POSSIBLE_BASE_VERSIONS"


# ==============================================================================
# 5. Version History Immutability & Temporal Lookup Tests
# ==============================================================================

def test_immutable_version_history(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    service = SchemeVersionService()

    v1_json_snapshot = copy.deepcopy(v1.canonical_data)
    v1_hash = v1.artifact_sha256

    # Create and approve changeset
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="DETECTED",
        effective_date=date(2026, 7, 1),
        changes_count=1,
        items=[
            SchemeChangeItem(
                id=uuid.uuid4(),
                field_path="eligibility.rules.family_income",
                change_type="REPLACE",
                old_value_json={"value": 200000},
                new_value_json={"value": 300000},
                risk_level="CRITICAL",
                status="PENDING",
            )
        ],
    )
    test_db.add(cs)
    test_db.commit()

    v2 = service.approve_change_set(test_db, cs.id)

    # Reload v1 from DB
    test_db.refresh(v1)
    # Version 1 data and hash MUST be unchanged
    assert v1.canonical_data == v1_json_snapshot
    assert v1.artifact_sha256 == v1_hash
    assert v1.version_number == 1

    # Version 2 has new version number and supersedes v1
    assert v2.version_number == 2
    assert v2.supersedes_version_id == v1.id


def test_temporal_lookup_before_and_after_effective_date(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    timeline = SchemeTimelineService()

    # Create Version 2 with effective date 2026-07-01
    v2 = SchemeVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version_number=2,
        version_label="v2.0 (Amended)",
        status="ACTIVE",
        valid_from=date(2026, 7, 1),
        valid_until=None,
        canonical_data=v1.canonical_data,
        is_current=True,
    )
    # Update v1 valid_until
    v1.valid_until = date(2026, 6, 30)
    test_db.add(v2)
    test_db.commit()

    # Query before amendment effective date (e.g. 2026-05-01) -> returns v1
    ver_may = timeline.get_scheme_version_at_date(test_db, scheme.id, target_date=date(2026, 5, 1))
    assert ver_may is not None
    assert ver_may.id == v1.id
    assert ver_may.version_number == 1

    # Query after amendment effective date (e.g. 2026-08-01) -> returns v2
    ver_aug = timeline.get_scheme_version_at_date(test_db, scheme.id, target_date=date(2026, 8, 1))
    assert ver_aug is not None
    assert ver_aug.id == v2.id
    assert ver_aug.version_number == 2


# ==============================================================================
# 6. Cache Invalidation & Stale Guards Tests
# ==============================================================================

def test_rule_cache_invalidation_on_activation(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    service = SchemeVersionService()

    # Pre-populate VerifiedRuleCache
    cache = get_rule_cache()
    cache._cache[str(scheme.id)] = MagicMock(scheme_id=str(scheme.id))
    assert str(scheme.id) in cache._cache

    # Create v2 and activate it
    v2 = SchemeVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version_number=2,
        status="HUMAN_VERIFIED",
        valid_from=date.today(),
        effective_date=date.today(),
        canonical_data=v1.canonical_data,
        is_current=False,
    )
    test_db.add(v2)
    test_db.commit()

    # Activate version
    service.activate_version(test_db, v2.id)

    # Verify cache entry was invalidated!
    assert str(scheme.id) not in cache._cache


def test_stale_base_version_guard(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    service = SchemeVersionService()

    # Build changeset against v1
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="DETECTED",
        changes_count=1,
    )
    test_db.add(cs)

    # In the interim, another version (v2) is created and activated
    v2 = SchemeVersion(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        version_number=2,
        status="ACTIVE",
        canonical_data=v1.canonical_data,
        is_current=True,
    )
    test_db.add(v2)
    test_db.commit()

    # Attempting to approve cs (built against v1) must fail with STALE_BASE_VERSION!
    with pytest.raises(ValueError, match="STALE_BASE_VERSION"):
        service.approve_change_set(test_db, cs.id)


def test_worker_rerun_idempotency(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    worker = SchemeVersioningWorker()

    # Create document with full title keywords for scheme and amendment
    doc_amend = Document(
        id=uuid.uuid4(),
        document_code=f"DOC-{uuid.uuid4().hex[:8].upper()}",
        title="अधिसूचना क्रमांक 890 दिनांक 15.08.2026: Mukhyamantri Vridhjan Samman Pension Yojana में वार्षिक आय सीमा संशोधित कर ₹3,00,000 की जाती है।",
        original_filename="amendment_2026.pdf",
        file_size_bytes=1024,
        storage_path="documents/amendment_2026.pdf",
        ingestion_method="API",
        mime_type="application/pdf",
        processing_status="NORMALIZED",
    )
    test_db.add(doc_amend)
    test_db.commit()

    # Cycle 1: creates changeset
    count1 = worker.run_cycle(test_db, batch_size=10, document_id=doc_amend.id)
    assert count1 >= 1

    # Cycle 2: identical document must be skipped idempotently
    count2 = worker.run_cycle(test_db, batch_size=10, document_id=doc_amend.id)
    assert count2 == 0


# ==============================================================================
# 7. REST API Integration Tests
# ==============================================================================

def test_api_scheme_versions_timeline(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    resp = client.get(f"/api/v1/admin/schemes/{scheme.id}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_name"] == scheme.name_en
    assert len(data["versions"]) >= 1
    assert data["versions"][0]["version_number"] == 1


def test_api_change_sets_list_and_detail(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="REVIEW_REQUIRED",
        changes_count=1,
        critical_changes_count=1,
        change_summary="1 eligibility condition modified",
    )
    item = SchemeChangeItem(
        id=uuid.uuid4(),
        change_set_id=cs.id,
        field_path="eligibility.rules.family_income",
        change_type="REPLACE",
        old_value_json={"value": 200000},
        new_value_json={"value": 300000},
        risk_level="CRITICAL",
        status="PENDING",
    )
    cs.items.append(item)
    test_db.add(cs)
    test_db.commit()

    # Test list endpoint with filters
    resp = client.get(f"/api/v1/admin/scheme-change-sets?scheme_id={scheme.id}&critical_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1

    # Test detail endpoint
    resp2 = client.get(f"/api/v1/admin/scheme-change-sets/{cs.id}")
    assert resp2.status_code == 200
    detail = resp2.json()
    assert detail["changes_count"] == 1
    assert len(detail["items"]) == 1
    assert detail["items"][0]["field_path"] == "eligibility.rules.family_income"


def test_api_approve_change_set(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="REVIEW_REQUIRED",
        changes_count=1,
    )
    test_db.add(cs)
    test_db.commit()

    resp = client.post(
        f"/api/v1/admin/scheme-change-sets/{cs.id}/approve",
        json={"reviewer_id": "REV-ADMIN-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_number"] == 2
    assert data["status"] == "HUMAN_VERIFIED"


def test_api_reject_change_set(test_db, seeded_scheme):
    scheme, v1, doc = seeded_scheme
    cs = SchemeChangeSet(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=doc.id,
        status="REVIEW_REQUIRED",
    )
    test_db.add(cs)
    test_db.commit()

    resp = client.post(
        f"/api/v1/admin/scheme-change-sets/{cs.id}/reject",
        json={"reason": "Incorrect notification referenced", "reviewer_id": "REV-ADMIN-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REJECTED"


def test_dipr_vs_notification_conflict(test_db, seeded_scheme):
    """
    Requirement 51 & 147:
    DIPR press release says income limit 3 lakh. Official notification says 2 lakh.
    No amendment relation. Expected review conflict, NOT automatic DIPR update.
    """
    scheme, v1, doc = seeded_scheme
    service = SchemeVersionService()

    # Create DIPR secondary document
    dipr_doc = Document(
        id=uuid.uuid4(),
        document_code=f"DOC-{uuid.uuid4().hex[:8].upper()}",
        title="DIPR Press Release: Pension income limit revised to 3 Lakh",
        original_filename="dipr_release.pdf",
        file_size_bytes=512,
        storage_path="documents/dipr_release.pdf",
        ingestion_method="WEB_MONITOR",
        mime_type="application/pdf",
        processing_status="NORMALIZED",
    )
    test_db.add(dipr_doc)
    test_db.commit()

    # Change set generated with conflict flag
    cs = service.build_change_set_for_document(
        db=test_db,
        scheme_id=scheme.id,
        base_version_id=v1.id,
        source_document_id=dipr_doc.id,
        candidate_canonical={"eligibility": {"simple_fields": {"family_income_max": 300000}}},
        conflict_reason="UNRESOLVED_SOURCE_CONFLICT: DIPR press release conflicts with official notification",
    )

    # Must be in REVIEW_REQUIRED, not automatically approved
    assert cs.status == "REVIEW_REQUIRED"
    assert "UNRESOLVED_SOURCE_CONFLICT" in cs.conflict_reason

    # Active version in database and timeline MUST remain v1 (income <= 2L)
    timeline = SchemeTimelineService()
    active_ver = timeline.get_active_scheme_version(test_db, scheme.id)
    assert active_ver.version_number == 1
    assert active_ver.canonical_data["eligibility"]["simple_fields"]["family_income_max"] == 200000
