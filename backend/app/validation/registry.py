from dataclasses import dataclass
from typing import Dict, Optional
from app.validation.schemas import ValidationSeverity


@dataclass(frozen=True)
class ValidationRuleDef:
    code: str
    category: str
    description: str
    default_severity: ValidationSeverity


VALIDATION_RULES: Dict[str, ValidationRuleDef] = {
    # Schema Rules
    "SCHEMA_INVALID": ValidationRuleDef(
        code="SCHEMA_INVALID",
        category="schema",
        description="Canonical scheme draft failed Pydantic schema validation or is malformed JSON.",
        default_severity=ValidationSeverity.BLOCKER,
    ),
    "REQUIRED_FIELD_MISSING": ValidationRuleDef(
        code="REQUIRED_FIELD_MISSING",
        category="schema",
        description="A required canonical top-level attribute or structure is missing.",
        default_severity=ValidationSeverity.BLOCKER,
    ),

    # Evidence Rules
    "EVIDENCE_REF_MISSING": ValidationRuleDef(
        code="EVIDENCE_REF_MISSING",
        category="evidence",
        description="A mandatory factual field (eligibility, benefit, document, date) has no evidence reference.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "EVIDENCE_REGISTRY_MISSING": ValidationRuleDef(
        code="EVIDENCE_REGISTRY_MISSING",
        category="evidence",
        description="An evidence reference ID was cited but does not exist in the draft's evidence registry.",
        default_severity=ValidationSeverity.BLOCKER,
    ),
    "EVIDENCE_PAGE_INVALID": ValidationRuleDef(
        code="EVIDENCE_PAGE_INVALID",
        category="evidence",
        description="Referenced evidence page number is <= 0 or exceeds the source document's page count.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "SOURCE_BLOCK_MISSING": ValidationRuleDef(
        code="SOURCE_BLOCK_MISSING",
        category="evidence",
        description="Evidence source block ID does not exist in the parsed document structure.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "CHUNK_INVALID": ValidationRuleDef(
        code="CHUNK_INVALID",
        category="evidence",
        description="Evidence chunk ID does not exist or evidence block/page does not belong to the chunk.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "DOCUMENT_MISMATCH": ValidationRuleDef(
        code="DOCUMENT_MISMATCH",
        category="evidence",
        description="Evidence item is linked to a different document ID than the scheme draft.",
        default_severity=ValidationSeverity.BLOCKER,
    ),
    "LOW_CONFIDENCE_OCR_EVIDENCE": ValidationRuleDef(
        code="LOW_CONFIDENCE_OCR_EVIDENCE",
        category="evidence",
        description="Evidence was produced by OCR with low extraction confidence.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "LOW_CONFIDENCE_NUMERIC_OCR": ValidationRuleDef(
        code="LOW_CONFIDENCE_NUMERIC_OCR",
        category="evidence",
        description="A sensitive numeric fact (income, age, benefit amount) relies on low-confidence OCR evidence.",
        default_severity=ValidationSeverity.ERROR,
    ),

    # Numbers Rules
    "AGE_NEGATIVE": ValidationRuleDef(
        code="AGE_NEGATIVE",
        category="numbers",
        description="Age condition value cannot be negative.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "AGE_SUSPICIOUS": ValidationRuleDef(
        code="AGE_SUSPICIOUS",
        category="numbers",
        description="Age condition value exceeds reasonable human upper bound (e.g. > 125 years).",
        default_severity=ValidationSeverity.WARNING,
    ),
    "AGE_RANGE_INVALID": ValidationRuleDef(
        code="AGE_RANGE_INVALID",
        category="numbers",
        description="Minimum age cannot exceed maximum age boundary.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "INCOME_NEGATIVE": ValidationRuleDef(
        code="INCOME_NEGATIVE",
        category="numbers",
        description="Income eligibility limit cannot be negative.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "INCOME_PERIOD_MISMATCH": ValidationRuleDef(
        code="INCOME_PERIOD_MISMATCH",
        category="numbers",
        description="Income field naming (e.g. annual_income) conflicts with periodicity (e.g. MONTHLY).",
        default_severity=ValidationSeverity.WARNING,
    ),
    "INCOME_EXTREME_VALUE": ValidationRuleDef(
        code="INCOME_EXTREME_VALUE",
        category="numbers",
        description="Income limit value is suspiciously high (e.g. > 10 Crore INR) for welfare criteria.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "PERCENTAGE_OUT_OF_RANGE": ValidationRuleDef(
        code="PERCENTAGE_OUT_OF_RANGE",
        category="numbers",
        description="Normalized percentage value must fall between 0 and 100 inclusive.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "CURRENCY_MISSING": ValidationRuleDef(
        code="CURRENCY_MISSING",
        category="numbers",
        description="A monetary benefit or fee amount is specified without currency indication.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "LAND_MEASUREMENT_NEGATIVE": ValidationRuleDef(
        code="LAND_MEASUREMENT_NEGATIVE",
        category="numbers",
        description="Land holding requirement cannot be negative.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "LAND_UNIT_UNKNOWN": ValidationRuleDef(
        code="LAND_UNIT_UNKNOWN",
        category="numbers",
        description="Land holding specification uses an unrecognized unit of measurement.",
        default_severity=ValidationSeverity.WARNING,
    ),

    # Geography Rules
    "DISTRICT_UNKNOWN": ValidationRuleDef(
        code="DISTRICT_UNKNOWN",
        category="geography",
        description="Normalized district name is not found in the Rajasthan district reference dataset.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "DISTRICT_REVIEW_REQUIRED": ValidationRuleDef(
        code="DISTRICT_REVIEW_REQUIRED",
        category="geography",
        description="District is recognized as historical or reorganized and requires reviewer confirmation.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "STATE_CONFLICT": ValidationRuleDef(
        code="STATE_CONFLICT",
        category="geography",
        description="Target scope specifies a state other than Rajasthan for a state scheme.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "SCHEME_ORIGIN_INVALID": ValidationRuleDef(
        code="SCHEME_ORIGIN_INVALID",
        category="geography",
        description="Scheme origin string is not one of the controlled enum values.",
        default_severity=ValidationSeverity.ERROR,
    ),

    # Date Rules
    "DATE_INVALID": ValidationRuleDef(
        code="DATE_INVALID",
        category="dates",
        description="Extracted date is not a valid real calendar date (e.g. 2026-02-30).",
        default_severity=ValidationSeverity.ERROR,
    ),
    "DATE_RANGE_INVALID": ValidationRuleDef(
        code="DATE_RANGE_INVALID",
        category="dates",
        description="Start date chronologically exceeds end date (e.g. valid_from > valid_until).",
        default_severity=ValidationSeverity.ERROR,
    ),

    # Eligibility & Tree Rules
    "OPERATOR_INCOMPATIBLE": ValidationRuleDef(
        code="OPERATOR_INCOMPATIBLE",
        category="eligibility",
        description="Operator is not compatible with the field data type (e.g. gender GTE FEMALE).",
        default_severity=ValidationSeverity.ERROR,
    ),
    "RULE_VALUE_MISSING": ValidationRuleDef(
        code="RULE_VALUE_MISSING",
        category="eligibility",
        description="Eligibility condition requires a value for this operator, but value is null.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "RULE_VALUE_EMPTY": ValidationRuleDef(
        code="RULE_VALUE_EMPTY",
        category="eligibility",
        description="IN or NOT_IN operator requires a non-empty list of values.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "RULE_GROUP_EMPTY": ValidationRuleDef(
        code="RULE_GROUP_EMPTY",
        category="eligibility",
        description="AND or OR composite rule group must contain at least one child element.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "RULE_NOT_INVALID": ValidationRuleDef(
        code="RULE_NOT_INVALID",
        category="eligibility",
        description="NOT logical group must contain exactly one child element.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "RULE_DEPTH_EXCEEDED": ValidationRuleDef(
        code="RULE_DEPTH_EXCEEDED",
        category="eligibility",
        description="Rule tree exceeds the maximum allowed nesting depth limit.",
        default_severity=ValidationSeverity.BLOCKER,
    ),
    "CONTRADICTORY_RULES": ValidationRuleDef(
        code="CONTRADICTORY_RULES",
        category="eligibility",
        description="Mutually exclusive or contradictory conditions detected within the same AND group.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "REDUNDANT_RULE": ValidationRuleDef(
        code="REDUNDANT_RULE",
        category="eligibility",
        description="Redundant or subsumed condition found in the same rule group.",
        default_severity=ValidationSeverity.INFO,
    ),
    "DOUBLE_NEGATION_SUSPICIOUS": ValidationRuleDef(
        code="DOUBLE_NEGATION_SUSPICIOUS",
        category="eligibility",
        description="Nested NOT(NOT(...)) condition detected; verify extraction logic.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "ELIGIBILITY_EXCLUSION_CONFLICT": ValidationRuleDef(
        code="ELIGIBILITY_EXCLUSION_CONFLICT",
        category="eligibility",
        description="Identical condition appears in both eligibility inclusion and exclusion rules.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "CUSTOM_FIELD_REQUIRED": ValidationRuleDef(
        code="CUSTOM_FIELD_REQUIRED",
        category="eligibility",
        description="Eligibility uses a custom condition requiring citizen dynamic input.",
        default_severity=ValidationSeverity.INFO,
    ),
    "UNSUPPORTED_FOR_AUTOMATIC_ELIGIBILITY": ValidationRuleDef(
        code="UNSUPPORTED_FOR_AUTOMATIC_ELIGIBILITY",
        category="eligibility",
        description="Condition is unstructured or unsupported for automatic execution; review required.",
        default_severity=ValidationSeverity.WARNING,
    ),

    # Benefit Rules
    "BENEFIT_NEGATIVE_AMOUNT": ValidationRuleDef(
        code="BENEFIT_NEGATIVE_AMOUNT",
        category="benefits",
        description="Benefit amount cannot be negative.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "BENEFIT_TYPE_INCONSISTENT": ValidationRuleDef(
        code="BENEFIT_TYPE_INCONSISTENT",
        category="benefits",
        description="Benefit type appears inconsistent with specified amount, currency, or description.",
        default_severity=ValidationSeverity.WARNING,
    ),

    # Document Rules
    "DOCUMENT_TYPE_INVALID": ValidationRuleDef(
        code="DOCUMENT_TYPE_INVALID",
        category="documents",
        description="Required document type does not match controlled document registry enums.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "DUPLICATE_DOCUMENT_REQUIREMENT": ValidationRuleDef(
        code="DUPLICATE_DOCUMENT_REQUIREMENT",
        category="documents",
        description="Multiple required document entries map to the same canonical document type.",
        default_severity=ValidationSeverity.INFO,
    ),

    # Application & Contact Rules
    "APPLICATION_URL_UNSAFE": ValidationRuleDef(
        code="APPLICATION_URL_UNSAFE",
        category="application",
        description="Application portal URL uses an unsafe or disallowed URI scheme (must be http/https).",
        default_severity=ValidationSeverity.BLOCKER,
    ),
    "CONTACT_INVALID": ValidationRuleDef(
        code="CONTACT_INVALID",
        category="application",
        description="Contact email address or telephone number format is malformed.",
        default_severity=ValidationSeverity.WARNING,
    ),

    # Conflict Rules
    "UNRESOLVED_CRITICAL_CONFLICT": ValidationRuleDef(
        code="UNRESOLVED_CRITICAL_CONFLICT",
        category="conflicts",
        description="Unresolved conflict exists for critical eligibility criteria, age, income, or benefits.",
        default_severity=ValidationSeverity.ERROR,
    ),
    "UNRESOLVED_CONFLICT": ValidationRuleDef(
        code="UNRESOLVED_CONFLICT",
        category="conflicts",
        description="Unresolved factual conflict detected across document chunks.",
        default_severity=ValidationSeverity.WARNING,
    ),

    # Identity Rules
    "SCHEME_NAME_MISSING": ValidationRuleDef(
        code="SCHEME_NAME_MISSING",
        category="identity",
        description="Scheme draft is missing both a detected name and official title.",
        default_severity=ValidationSeverity.WARNING,
    ),
    "DEPARTMENT_UNRESOLVED": ValidationRuleDef(
        code="DEPARTMENT_UNRESOLVED",
        category="identity",
        description="Extracted department name could not be resolved to an official registry department ID.",
        default_severity=ValidationSeverity.INFO,
    ),
}


def get_rule_def(code: str) -> Optional[ValidationRuleDef]:
    """Retrieve rule definition by code."""
    return VALIDATION_RULES.get(code)


def get_severity(code: str, override_severity: Optional[ValidationSeverity] = None) -> ValidationSeverity:
    """Retrieve severity for rule code, with optional override."""
    if override_severity:
        return override_severity
    rule = VALIDATION_RULES.get(code)
    return rule.default_severity if rule else ValidationSeverity.ERROR
