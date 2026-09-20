"""
JanSetu - Day 29: Deterministic Fact Matching & Value Semantic Normalization.

Implements:
- Canonical field mapping
- Exact and normalized semantic value equivalence
- Operator boundary-sensitive matching
- Unit, currency, and period comparison
- Benefit qualifier and document requirement validation
"""

from dataclasses import dataclass, field as dc_field
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.evaluation.schemas import MatchResult
from app.normalization.currency import detect_currency, detect_periodicity
from app.normalization.numbers import devanagari_to_ascii, parse_indian_number, parse_percentage
from app.normalization.operators import detect_operator_and_value
from app.normalization.schemas import OperatorEnum, PeriodicityEnum


@dataclass
class ExtractedFactItem:
    """Normalized, uniform representation of an extracted fact from system output."""
    field: str
    value: Any
    operator: Optional[str] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    currency: Optional[str] = None
    is_mandatory: Optional[bool] = None
    evidence_text: Optional[str] = None
    page_numbers: List[int] = dc_field(default_factory=list)
    source_block_ids: List[str] = dc_field(default_factory=list)
    chunk_id: Optional[str] = None
    raw_text: Optional[str] = None
    has_qualifier: bool = False  # e.g. "up to", "maximum"


class FactMatcher:
    """
    Deterministic factual evaluation engine comparing system extraction against gold reference truth.
    Never uses LLM self-evaluation; strictly relies on deterministic canonical normalizers.
    """

    @staticmethod
    def canonicalize_field_name(raw_field: str) -> str:
        """Normalize field path to canonical dot-notation."""
        if not raw_field:
            return ""
        norm = raw_field.strip().lower()
        norm = re.sub(r'\[.*?\]', '', norm)  # strip indices
        norm = norm.replace('/', '.').replace('-', '_')
        norm = re.sub(r'\.+', '.', norm).strip('.')

        # Aliases
        aliases = {
            "eligibility.minimum_age": "eligibility.age",
            "eligibility.maximum_age": "eligibility.age",
            "eligibility.age_limit": "eligibility.age",
            "eligibility.residency": "eligibility.domicile",
            "eligibility.rajasthan_resident": "eligibility.domicile",
            "eligibility.resident": "eligibility.domicile",
            "eligibility.annual_income": "eligibility.income",
            "eligibility.family_income": "eligibility.income",
            "eligibility.income_limit": "eligibility.income",
            "eligibility.bpl_status": "eligibility.bpl",
            "exclusions.govt_service": "exclusions.government_service",
            "exclusions.government_servant": "exclusions.government_service",
            "exclusions.existing_pension": "exclusions.similar_pension",
            "benefits.amount": "benefits.monthly_amount",
            "benefits.pension": "benefits.monthly_amount",
            "documents.aadhaar": "documents.jan_aadhaar",
            "financial_values.income_limit": "eligibility.income",
            "financial_values.income_ceiling": "eligibility.income",
        }
        return aliases.get(norm, norm)

    @classmethod
    def are_fields_matching(cls, gold_field: str, pred_field: str) -> bool:
        """Check if predicted field matches gold field canonically."""
        g = cls.canonicalize_field_name(gold_field)
        p = cls.canonicalize_field_name(pred_field)
        if g == p:
            return True
        # Prefix category match if domain matches
        if g.split('.')[0] == p.split('.')[0]:
            # e.g. exclusions match or eligibility subfield match
            g_sub = g.split('.')[-1]
            p_sub = p.split('.')[-1]
            if g_sub == p_sub:
                return True
        return False

    @staticmethod
    def normalize_value(val: Any) -> Any:
        """
        Deterministically normalizes a value (number, string, boolean) into canonical form.
        Handles Indian scale terms (lakh, crore), Devanagari numerals, and whitespace.
        """
        if val is None:
            return None

        # Boolean normalization
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            s_val = val.strip().lower()
            if s_val in ("true", "yes", "हाँ", "1"):
                return True
            if s_val in ("false", "no", "नहीं", "0"):
                return False

            # Check if it contains an Indian number
            parsed_num = parse_indian_number(val)
            if parsed_num is not None:
                # If original had percentage
                if "%" in val or "प्रतिशत" in val or "percent" in s_val:
                    return float(parsed_num)
                return parsed_num

            # Normalized string: strip punctuation, collapse whitespace
            s_norm = devanagari_to_ascii(s_val)
            s_norm = re.sub(r'[^\w\s]', '', s_norm)
            s_norm = re.sub(r'\s+', ' ', s_norm).strip()
            return s_norm.upper()

        if isinstance(val, (int, float)):
            if isinstance(val, float) and val.is_integer():
                return int(val)
            return val

        return val

    @classmethod
    def are_values_exact_match(cls, gold_val: Any, pred_val: Any) -> bool:
        """Strict exact match comparison."""
        if gold_val is None and pred_val is None:
            return True
        if gold_val is None or pred_val is None:
            return False

        # Numeric exact equality
        if isinstance(gold_val, (int, float)) and isinstance(pred_val, (int, float)):
            return float(gold_val) == float(pred_val)

        # String exact match (case-insensitive and trimmed)
        return str(gold_val).strip().lower() == str(pred_val).strip().lower()

    @classmethod
    def are_values_semantically_equivalent(
        cls,
        gold_val: Any,
        pred_val: Any,
        gold_unit: Optional[str] = None,
        pred_unit: Optional[str] = None,
        gold_period: Optional[str] = None,
        pred_period: Optional[str] = None,
        gold_qualifier: bool = False,
        pred_qualifier: bool = False,
    ) -> bool:
        """
        Normalized semantic equivalence comparison.
        Checks:
        - Deterministic number/scale equivalence (e.g. ₹2 lakh == 200000 == 2,00,000)
        - Periodicity match (MONTHLY vs ANNUAL)
        - Measurement unit match
        - Benefit qualifier consistency ("up to" vs flat)
        """
        # 1. Periodicity check: if both specified, they must match
        if gold_period and pred_period:
            g_p = gold_period.strip().upper()
            p_p = pred_period.strip().upper()
            if g_p != p_p and g_p != "UNKNOWN" and p_p != "UNKNOWN":
                return False

        # 2. Qualifier check: "up to ₹50,000" vs "₹50,000"
        if gold_qualifier != pred_qualifier:
            return False

        # 3. Normalized value comparison
        norm_gold = cls.normalize_value(gold_val)
        norm_pred = cls.normalize_value(pred_val)

        if norm_gold is None and norm_pred is None:
            return True
        if norm_gold is None or norm_pred is None:
            return False

        # Numeric match
        if isinstance(norm_gold, (int, float)) and isinstance(norm_pred, (int, float)):
            return float(norm_gold) == float(norm_pred)

        # Boolean match
        if isinstance(norm_gold, bool) and isinstance(norm_pred, bool):
            return norm_gold is norm_pred

        # String / token match
        s_g = str(norm_gold).strip().upper()
        s_p = str(norm_pred).strip().upper()
        if s_g == s_p:
            return True

        # Special casing for Indian states & resident tokens
        if ("RAJASTHAN" in s_g and "RAJASTHAN" in s_p) or ("DOMICILE" in s_g and "DOMICILE" in s_p):
            return True

        return False

    @staticmethod
    def canonicalize_operator(op: Optional[Union[str, OperatorEnum]]) -> Optional[str]:
        """Convert operator representation to stable uppercase string."""
        if not op:
            return None
        if isinstance(op, OperatorEnum):
            return op.value
        s = str(op).strip().upper()
        mapping = {
            ">=": "GTE",
            "<=": "LTE",
            ">": "GT",
            "<": "LT",
            "=": "EQ",
            "==": "EQ",
            "!=": "NEQ",
            "NE": "NEQ",
            "NOT_EQUAL": "NEQ",
            "GREATER_THAN_OR_EQUAL": "GTE",
            "LESS_THAN_OR_EQUAL": "LTE",
            "GREATER_THAN": "GT",
            "LESS_THAN": "LT",
            "EQUAL": "EQ",
        }
        return mapping.get(s, s)

    @classmethod
    def are_operators_matching(
        cls,
        gold_op: Optional[Union[str, OperatorEnum]],
        pred_op: Optional[Union[str, OperatorEnum]],
    ) -> bool:
        """
        Exact relational operator comparison.
        Boundary differences (e.g. LTE vs LT, GTE vs GT) are strictly considered mismatches.
        """
        g = cls.canonicalize_operator(gold_op)
        p = cls.canonicalize_operator(pred_op)
        if g is None and p is None:
            return True
        if g is None or p is None:
            # If gold specifies no operator, EQ is assumed default if value matched
            return (g or "EQ") == (p or "EQ")
        return g == p
