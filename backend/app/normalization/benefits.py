import re
from typing import List, Optional

from app.normalization.currency import detect_currency, detect_periodicity
from app.normalization.numbers import parse_indian_number
from app.normalization.schemas import BenefitTypeEnum, CanonicalBenefit, PeriodicityEnum


def normalize_benefit(
    raw_text: str,
    raw_amount: Optional[str],
    frequency_text: Optional[str],
    description: Optional[str],
    benefit_type_hint: Optional[str],
    evidence_refs: List[str],
    benefit_id: str,
) -> CanonicalBenefit:
    """
    Normalize benefit extraction into CanonicalBenefit.
    Never invents an amount if none was specified in the raw text.
    """
    full_text = f"{raw_text} {raw_amount or ''} {frequency_text or ''} {description or ''}".lower()

    # Determine benefit type
    btype = BenefitTypeEnum.OTHER
    if re.search(r'(पेंशन|pension)', full_text):
        btype = BenefitTypeEnum.PENSION
    elif re.search(r'(छात्रवृत्ति|scholarship|stipend)', full_text):
        btype = BenefitTypeEnum.SCHOLARSHIP
    elif re.search(r'(अनुदान|सब्सिडी|subsidy)', full_text):
        btype = BenefitTypeEnum.SUBSIDY
    elif re.search(r'(बीमा|insurance|coverage)', full_text):
        btype = BenefitTypeEnum.INSURANCE
    elif re.search(r'(ऋण|loan)', full_text):
        btype = BenefitTypeEnum.LOAN
    elif re.search(r'(पुनर्भरण|reimbursement)', full_text):
        btype = BenefitTypeEnum.REIMBURSEMENT
    elif re.search(r'(वित्तीय\s*सहायता|नकद|cash|financial\s*assistance|grant)', full_text):
        btype = BenefitTypeEnum.CASH
    elif re.search(r'(राशन|किट|उपकरण|in-kind|material)', full_text):
        btype = BenefitTypeEnum.IN_KIND
    elif re.search(r'(छूट|concession)', full_text):
        btype = BenefitTypeEnum.CONCESSION
    elif benefit_type_hint:
        hint_lower = benefit_type_hint.lower()
        for member in BenefitTypeEnum:
            if member.value.lower() in hint_lower:
                btype = member
                break

    # Parse amount
    amount = None
    target_amount_str = raw_amount if raw_amount else raw_text
    parsed_num = parse_indian_number(target_amount_str)
    # Ensure parsed number is reasonable as a benefit amount, not e.g. a page number or year
    if parsed_num is not None and parsed_num not in [2024, 2025, 2026, 2027]:
        amount = float(parsed_num)

    # Detect currency
    currency = detect_currency(target_amount_str) or "INR"

    # Detect frequency
    periodicity = PeriodicityEnum.UNKNOWN
    if frequency_text:
        periodicity = detect_periodicity(frequency_text)
    if periodicity == PeriodicityEnum.UNKNOWN:
        periodicity = detect_periodicity(raw_text)

    return CanonicalBenefit(
        benefit_id=benefit_id,
        type=btype,
        amount=amount,
        currency=currency,
        frequency=periodicity,
        description=description or raw_text,
        raw_amount_text=raw_amount,
        raw_text=raw_text,
        evidence_refs=evidence_refs,
    )
