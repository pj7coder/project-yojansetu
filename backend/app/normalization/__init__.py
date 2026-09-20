"""Canonical Scheme Schema and Normalization Layer for JanSetu (Day 10)."""
from app.normalization.aggregator import DocumentSchemeAggregator
from app.normalization.benefits import normalize_benefit
from app.normalization.conflicts import detect_conflicts, merge_identical_conditions
from app.normalization.currency import detect_currency, detect_periodicity
from app.normalization.dates import parse_date_expression
from app.normalization.documents import normalize_document_requirement
from app.normalization.eligibility import build_eligibility_tree, normalize_single_criterion
from app.normalization.numbers import devanagari_to_ascii, parse_indian_number, parse_percentage
from app.normalization.operators import detect_operator_and_value
from app.normalization.schemas import (
    BenefitTypeEnum,
    CanonicalApplication,
    CanonicalBenefit,
    CanonicalContact,
    CanonicalDefinition,
    CanonicalDocument,
    CanonicalEligibility,
    CanonicalExclusion,
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
    NormalizationMethod,
    NormalizationStatus,
    NormalizationSummary,
    OperatorEnum,
    PeriodicityEnum,
    RuleGroup,
    SchemeNameDetail,
    SchemeOriginEnum,
)
from app.normalization.service import SchemeNormalizationService

__all__ = [
    "DocumentSchemeAggregator",
    "SchemeNormalizationService",
    "parse_indian_number",
    "devanagari_to_ascii",
    "parse_percentage",
    "detect_currency",
    "detect_periodicity",
    "parse_date_expression",
    "detect_operator_and_value",
    "normalize_single_criterion",
    "build_eligibility_tree",
    "normalize_benefit",
    "normalize_document_requirement",
    "detect_conflicts",
    "merge_identical_conditions",
    "CanonicalSchemeDraft",
    "CanonicalIdentity",
    "CanonicalScope",
    "CanonicalEligibility",
    "EligibilityCondition",
    "RuleGroup",
    "CanonicalExclusion",
    "CanonicalBenefit",
    "CanonicalDocument",
    "CanonicalApplication",
    "CanonicalImportantDate",
    "CanonicalContact",
    "CanonicalDefinition",
    "EvidenceRegistryItem",
    "ConflictRecord",
    "ConflictValue",
    "NormalizationSummary",
    "OperatorEnum",
    "LogicalGroupType",
    "NormalizationStatus",
    "NormalizationMethod",
    "PeriodicityEnum",
    "BenefitTypeEnum",
    "DocumentTypeEnum",
    "SchemeOriginEnum",
    "SchemeNameDetail",
]
