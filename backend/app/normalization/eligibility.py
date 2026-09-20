import re
from typing import Any, Dict, List, Optional, Tuple

from app.normalization.currency import detect_currency, detect_periodicity
from app.normalization.numbers import devanagari_to_ascii, parse_indian_number, parse_percentage
from app.normalization.operators import detect_operator_and_value
from app.normalization.schemas import (
    CanonicalEligibility,
    EligibilityCondition,
    GenderEnum,
    LogicalGroupType,
    NormalizationMethod,
    NormalizationStatus,
    OperatorEnum,
    PeriodicityEnum,
    ResidencyTypeEnum,
    RuleGroup,
    SocialCategoryEnum,
)


def normalize_income_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """
    Normalize personal income vs family income condition accurately.
    Distinguishes applicant income from family income without collapsing them.
    """
    lower = text.lower()

    # Distinguish family income from individual income
    is_family = bool(re.search(r'(पारिवारिक|परिवार|family)', lower))
    field_name = "family_income" if is_family else "annual_income"

    op, val, unit = detect_operator_and_value(text)
    periodicity = detect_periodicity(text)

    # In Indian government schemes, if amount is large (e.g. >= 50,000) and unstated periodicity,
    # keep periodicity as UNKNOWN unless explicitly stated
    if periodicity == PeriodicityEnum.UNKNOWN and re.search(r'(वार्षिक|annual|प्रति\s*वर्ष)', lower):
        periodicity = PeriodicityEnum.ANNUAL
    elif periodicity == PeriodicityEnum.UNKNOWN and re.search(r'(मासिक|monthly|प्रति\s*माह)', lower):
        periodicity = PeriodicityEnum.MONTHLY

    return EligibilityCondition(
        condition_id=condition_id,
        field=field_name,
        operator=op,
        value=val,
        value_type="number",
        unit="INR",
        periodicity=periodicity,
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED if val is not None else NormalizationStatus.AMBIGUOUS,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_age_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize age eligibility with exact boundary handling."""
    op, val, unit = detect_operator_and_value(text)

    return EligibilityCondition(
        condition_id=condition_id,
        field="age",
        operator=op,
        value=val,
        value_type="range" if op == OperatorEnum.BETWEEN else "number",
        unit="years",
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED if val is not None else NormalizationStatus.AMBIGUOUS,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_residency_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize Rajasthan residency requirements preserving legal distinctions."""
    lower = text.lower()
    residency_type = ResidencyTypeEnum.UNKNOWN

    if re.search(r'(मूल\s*निवासी|स्थाई\s*निवासी|permanent\s*resident)', lower):
        residency_type = ResidencyTypeEnum.PERMANENT_RESIDENT
    elif re.search(r'(डोमिसाइल|domicile)', lower):
        residency_type = ResidencyTypeEnum.DOMICILE
    elif re.search(r'(निवासी|resident)', lower):
        residency_type = ResidencyTypeEnum.RESIDENT

    return EligibilityCondition(
        condition_id=condition_id,
        field="residency",
        operator=OperatorEnum.EQ,
        value="Rajasthan",
        value_type="string",
        unit=None,
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
        custom_field_name=residency_type.value,
    )


def normalize_gender_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize gender requirements."""
    lower = text.lower()
    gender = GenderEnum.UNKNOWN

    if re.search(r'(महिला|स्त्री|female|women|woman)', lower):
        gender = GenderEnum.FEMALE
    elif re.search(r'(पुरुष|male|men|man)', lower):
        gender = GenderEnum.MALE
    elif re.search(r'(सभी|any|both)', lower):
        gender = GenderEnum.ANY

    return EligibilityCondition(
        condition_id=condition_id,
        field="gender",
        operator=OperatorEnum.EQ,
        value=gender.value,
        value_type="string",
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED if gender != GenderEnum.UNKNOWN else NormalizationStatus.AMBIGUOUS,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_social_category_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize caste / social category criteria."""
    lower = text.lower()
    cats = []

    if re.search(r'\b(sc|अनुसूचित\s*जाति)\b', lower):
        cats.append(SocialCategoryEnum.SC.value)
    if re.search(r'\b(st|अनुसूचित\s*जनजाति)\b', lower):
        cats.append(SocialCategoryEnum.ST.value)
    if re.search(r'\b(obc|अन्य\s*पिछड़ा\s*वर्ग)\b', lower):
        cats.append(SocialCategoryEnum.OBC.value)
    if re.search(r'\b(ews|आर्थिक\s*रूप\s*से\s*कमजोर)\b', lower):
        cats.append(SocialCategoryEnum.EWS.value)
    if re.search(r'\b(general|सामान्य)\b', lower):
        cats.append(SocialCategoryEnum.GENERAL.value)
    if re.search(r'\b(minority|अल्पसंख्यक)\b', lower):
        cats.append(SocialCategoryEnum.MINORITY.value)

    if not cats:
        val = text.strip()
        op = OperatorEnum.EQ
    elif len(cats) == 1:
        val = cats[0]
        op = OperatorEnum.EQ
    else:
        val = cats
        op = OperatorEnum.IN

    return EligibilityCondition(
        condition_id=condition_id,
        field="social_category",
        operator=op,
        value=val,
        value_type="list" if op == OperatorEnum.IN else "string",
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED if cats else NormalizationStatus.AMBIGUOUS,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_disability_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize disability status and percentage."""
    pct = parse_percentage(text)
    if pct:
        val, _ = pct
        op, _, _ = detect_operator_and_value(text)
        return EligibilityCondition(
            condition_id=condition_id,
            field="disability_percentage",
            operator=op if op != OperatorEnum.EQ else OperatorEnum.GTE,
            value=val,
            value_type="number",
            unit="PERCENT",
            raw_text=text,
            normalization_status=NormalizationStatus.NORMALIZED,
            normalization_method=NormalizationMethod.DETERMINISTIC,
            evidence_refs=evidence_refs,
        )

    return EligibilityCondition(
        condition_id=condition_id,
        field="disability_status",
        operator=OperatorEnum.EQ,
        value=True,
        value_type="boolean",
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_bpl_condition(
    text: str,
    evidence_refs: List[str],
    condition_id: str,
) -> EligibilityCondition:
    """Normalize BPL (Below Poverty Line) cardholder status."""
    return EligibilityCondition(
        condition_id=condition_id,
        field="bpl_status",
        operator=OperatorEnum.EQ,
        value=True,
        value_type="boolean",
        raw_text=text,
        normalization_status=NormalizationStatus.NORMALIZED,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
    )


def normalize_single_criterion(
    raw_text: str,
    evidence_refs: List[str],
    idx: int,
) -> EligibilityCondition:
    """Route a single eligibility condition string to its domain normalizer."""
    cid = f"COND-{idx:03d}"
    lower = raw_text.lower()

    # Check for income
    if re.search(r'(आय|income|वेतन|salary|lakh|लाख)', lower) and not re.search(r'(marks|अंक|प्रतिशत|%)', lower):
        return normalize_income_condition(raw_text, evidence_refs, cid)

    # Check for age
    if re.search(r'(आयु|उम्र|age|वर्ष|साल|years?)', lower) and not re.search(r'(आय|income|अनुभव|experience)', lower):
        return normalize_age_condition(raw_text, evidence_refs, cid)

    # Check for residency
    if re.search(r'(निवासी|मूल\s*निवासी|resident|domicile|राजस्थान)', lower) and not re.search(r'(आय|income)', lower):
        return normalize_residency_condition(raw_text, evidence_refs, cid)

    # Check for gender
    if re.search(r'(महिला|स्त्री|पुरुष|female|women|woman|male)', lower):
        return normalize_gender_condition(raw_text, evidence_refs, cid)

    # Check for social category
    if re.search(r'(अनुसूचित|sc|st|obc|जाति|वर्ग|category|caste)', lower):
        return normalize_social_category_condition(raw_text, evidence_refs, cid)

    # Check for disability
    if re.search(r'(दिव्यांग|विकलांग|disability|disabled|विशेष\s*योग्यजन)', lower):
        return normalize_disability_condition(raw_text, evidence_refs, cid)

    # Check for BPL
    if re.search(r'\b(bpl|बीपीएल|गरीबी\s*रेखा)\b', lower):
        return normalize_bpl_condition(raw_text, evidence_refs, cid)

    # Custom condition fallback
    val = parse_indian_number(raw_text)
    op, _, _ = detect_operator_and_value(raw_text)
    return EligibilityCondition(
        condition_id=cid,
        field="CUSTOM",
        operator=op,
        value=val if val is not None else raw_text.strip(),
        value_type="number" if val is not None else "string",
        raw_text=raw_text,
        normalization_status=NormalizationStatus.NORMALIZED if val is not None else NormalizationStatus.AMBIGUOUS,
        normalization_method=NormalizationMethod.DETERMINISTIC,
        evidence_refs=evidence_refs,
        custom_field_name="general_requirement",
    )


def build_eligibility_tree(
    conditions: List[EligibilityCondition],
    overall_logical_structure: Optional[str] = None,
) -> CanonicalEligibility:
    """
    Construct canonical eligibility model and hierarchical rule tree.
    Preserves AND / OR structures and builds simple_fields quick-lookup map.
    """
    if not conditions:
        root = RuleGroup(type=LogicalGroupType.AND, children=[], raw_text="No eligibility conditions specified")
        return CanonicalEligibility(
            root_rule=root,
            simple_fields={},
            field_statuses={},
            missing_fields_behavior={
                "annual_income": "NOT_MENTIONED",
                "family_income": "NOT_MENTIONED",
                "age": "NOT_MENTIONED",
            },
        )

    # Check if any conditions are OR linked
    or_groups = []
    and_children = []

    i = 0
    while i < len(conditions):
        cond = conditions[i]
        raw_l = cond.raw_text.lower().strip()
        is_or_connector = (
            raw_l.endswith("अथवा")
            or raw_l.endswith(" or")
            or raw_l.endswith("या")
            or " अथवा " in raw_l
            or " or " in raw_l
        )
        if is_or_connector and (i + 1 < len(conditions)):
            or_items = [cond, conditions[i + 1]]
            i += 2
            while i < len(conditions) and (
                or_items[-1].raw_text.lower().strip().endswith("अथवा")
                or or_items[-1].raw_text.lower().strip().endswith("या")
            ):
                or_items.append(conditions[i])
                i += 1
            or_groups.append(
                RuleGroup(
                    type=LogicalGroupType.OR,
                    children=or_items,
                    logical_relationship="OR",
                    raw_text="OR conditional alternatives",
                )
            )
        elif "अथवा" in raw_l or " या " in raw_l or " or " in raw_l:
            or_groups.append(cond)
            i += 1
        else:
            and_children.append(cond)
            i += 1

    if or_groups and and_children:
        root_children = and_children + or_groups
        root = RuleGroup(
            type=LogicalGroupType.AND,
            children=root_children,
            logical_relationship="AND",
        )
    elif or_groups and not and_children:
        if len(or_groups) == 1 and isinstance(or_groups[0], RuleGroup):
            root = or_groups[0]
        else:
            root = RuleGroup(
                type=LogicalGroupType.OR,
                children=or_groups,
                logical_relationship="OR",
            )
    else:
        root = RuleGroup(
            type=LogicalGroupType.AND,
            children=conditions,
            logical_relationship="AND",
        )

    # Compile simple_fields quick lookups
    simple = {}
    statuses = {}
    for c in conditions:
        statuses[c.field] = c.normalization_status
        if c.field == "age":
            if c.operator in [OperatorEnum.GTE, OperatorEnum.GT]:
                simple["min_age"] = c.value
            elif c.operator in [OperatorEnum.LTE, OperatorEnum.LT]:
                simple["max_age"] = c.value
            elif c.operator == OperatorEnum.BETWEEN and isinstance(c.value, list) and len(c.value) == 2:
                simple["min_age"] = c.value[0]
                simple["max_age"] = c.value[1]
        elif c.field == "family_income":
            if c.operator in [OperatorEnum.LTE, OperatorEnum.LT]:
                simple["family_income_max"] = c.value
        elif c.field == "annual_income":
            if c.operator in [OperatorEnum.LTE, OperatorEnum.LT]:
                simple["annual_income_max"] = c.value
        elif c.field == "residency":
            simple["state"] = c.value
        elif c.field == "gender":
            simple["gender"] = c.value

    # Differentiate NOT_MENTIONED from NO_LIMIT
    missing_behavior = {}
    for key in ["annual_income", "family_income", "age", "gender"]:
        if key not in statuses:
            missing_behavior[key] = "NOT_MENTIONED"

    return CanonicalEligibility(
        root_rule=root,
        simple_fields=simple,
        field_statuses=statuses,
        missing_fields_behavior=missing_behavior,
    )
