import pytest

from app.normalization.eligibility import (
    build_eligibility_tree,
    normalize_age_condition,
    normalize_gender_condition,
    normalize_income_condition,
    normalize_residency_condition,
    normalize_single_criterion,
    normalize_social_category_condition,
)
from app.normalization.schemas import (
    LogicalGroupType,
    OperatorEnum,
    PeriodicityEnum,
    ResidencyTypeEnum,
    SocialCategoryEnum,
)


def test_personal_vs_family_income_separation():
    # Family income must NOT be mapped to applicant income
    c_fam = normalize_income_condition(
        text="परिवार की वार्षिक आय ₹2.5 लाख से अधिक नहीं होनी चाहिए",
        evidence_refs=["EVID-001"],
        condition_id="COND-001",
    )
    assert c_fam.field == "family_income"
    assert c_fam.operator == OperatorEnum.LTE
    assert c_fam.value == 250000
    assert c_fam.periodicity == PeriodicityEnum.ANNUAL

    # Applicant personal income
    c_indiv = normalize_income_condition(
        text="आवेदक की व्यक्तिगत मासिक आय ₹10,000 से कम होनी चाहिए",
        evidence_refs=["EVID-002"],
        condition_id="COND-002",
    )
    assert c_indiv.field == "annual_income"  # individual income
    assert c_indiv.operator == OperatorEnum.LT
    assert c_indiv.value == 10000
    assert c_indiv.periodicity == PeriodicityEnum.MONTHLY


def test_residency_and_domicile_condition():
    c_res = normalize_residency_condition(
        text="आवेदक राजस्थान का मूल निवासी होना चाहिए",
        evidence_refs=["EVID-003"],
        condition_id="COND-003",
    )
    assert c_res.field == "residency"
    assert c_res.value == "Rajasthan"
    assert c_res.custom_field_name == ResidencyTypeEnum.PERMANENT_RESIDENT.value
    assert c_res.raw_text == "आवेदक राजस्थान का मूल निवासी होना चाहिए"


def test_gender_and_social_category():
    # Gender
    c_gen = normalize_gender_condition(
        text="केवल महिला अभ्यर्थियों हेतु",
        evidence_refs=["EVID-004"],
        condition_id="COND-004",
    )
    assert c_gen.field == "gender"
    assert c_gen.value == "FEMALE"

    # Multiple social categories
    c_cat = normalize_social_category_condition(
        text="अनुसूचित जाति (SC) तथा अनुसूचित जनजाति (ST) के नागरिक",
        evidence_refs=["EVID-005"],
        condition_id="COND-005",
    )
    assert c_cat.field == "social_category"
    assert c_cat.operator == OperatorEnum.IN
    assert set(c_cat.value) == {SocialCategoryEnum.SC.value, SocialCategoryEnum.ST.value}


def test_disability_percentage():
    c_dis = normalize_single_criterion(
        raw_text="न्यूनतम 40 प्रतिशत दिव्यांगता प्रमाण पत्र",
        evidence_refs=["EVID-006"],
        idx=1,
    )
    assert c_dis.field == "disability_percentage"
    assert c_dis.operator == OperatorEnum.GTE
    assert c_dis.value == 40.0
    assert c_dis.unit == "PERCENT"


def test_complex_rule_tree_and_or_composition():
    # Scenario: Rajasthan resident AND (BPL cardholder OR Annual income <= 200000)
    c1 = normalize_single_criterion("राजस्थान का मूल निवासी होना अनिवार्य है", ["EVID-01"], 1)
    c2 = normalize_single_criterion("बीपीएल कार्डधारक परिवार अथवा", ["EVID-02"], 2)
    c3 = normalize_single_criterion("वार्षिक पारिवारिक आय ₹2 लाख से कम", ["EVID-03"], 3)

    eligibility = build_eligibility_tree([c1, c2, c3])
    root = eligibility.root_rule

    assert root.type == LogicalGroupType.AND
    assert len(root.children) == 2  # c1 and the nested OR group

    # Find the nested OR group
    or_groups = [ch for ch in root.children if hasattr(ch, "type") and ch.type == LogicalGroupType.OR]
    assert len(or_groups) == 1
    assert len(or_groups[0].children) == 2  # c2 and c3

    # Verify simple_fields contains quick lookups
    assert eligibility.simple_fields.get("state") == "Rajasthan"
    assert eligibility.simple_fields.get("family_income_max") == 200000


def test_missing_fields_behavior_differentiation():
    # Only residency provided
    c1 = normalize_single_criterion("राजस्थान का निवासी", ["EVID-01"], 1)
    eligibility = build_eligibility_tree([c1])

    # Unmentioned criteria should be explicitly marked NOT_MENTIONED, NOT 'NO_LIMIT'
    assert eligibility.missing_fields_behavior.get("age") == "NOT_MENTIONED"
    assert eligibility.missing_fields_behavior.get("annual_income") == "NOT_MENTIONED"
    assert eligibility.missing_fields_behavior.get("family_income") == "NOT_MENTIONED"


def test_custom_condition_preservation():
    c_custom = normalize_single_criterion(
        raw_text="पंजीकृत निर्माण श्रमिक के रूप में 90 दिन कार्य पूर्ण",
        evidence_refs=["EVID-010"],
        idx=5,
    )
    assert c_custom.field == "CUSTOM"
    assert c_custom.value == 90
    assert c_custom.raw_text == "पंजीकृत निर्माण श्रमिक के रूप में 90 दिन कार्य पूर्ण"
