import pytest

from app.normalization.benefits import normalize_benefit
from app.normalization.currency import detect_currency, detect_periodicity
from app.normalization.dates import parse_date_expression
from app.normalization.documents import normalize_document_requirement
from app.normalization.numbers import devanagari_to_ascii, parse_indian_number, parse_percentage
from app.normalization.operators import detect_operator_and_value
from app.normalization.schemas import BenefitTypeEnum, DocumentTypeEnum, OperatorEnum, PeriodicityEnum


def test_devanagari_numeral_conversion():
    assert devanagari_to_ascii("०१२३४५६७८९") == "0123456789"
    assert devanagari_to_ascii("६० वर्ष") == "60 वर्ष"
    assert devanagari_to_ascii("२.५ लाख") == "2.5 लाख"


def test_indian_number_scale_parsing():
    # Lakhs
    assert parse_indian_number("₹2 लाख") == 200000
    assert parse_indian_number("2 lakh") == 200000
    assert parse_indian_number("1.5 लाख") == 150000
    assert parse_indian_number("1.5 lakh") == 150000
    assert parse_indian_number("२ लाख") == 200000
    assert parse_indian_number("२.५ लाख") == 250000

    # Crores
    assert parse_indian_number("1 करोड़") == 10000000
    assert parse_indian_number("2.5 crore") == 25000000

    # Thousands
    assert parse_indian_number("50 हजार") == 50000
    assert parse_indian_number("50 thousand") == 50000

    # Comma formatting
    assert parse_indian_number("₹2,00,000") == 200000
    assert parse_indian_number("1,50,000") == 150000
    assert parse_indian_number("५०,०००") == 50000

    # Standard integers
    assert parse_indian_number("60 वर्ष") == 60
    assert parse_indian_number("६० वर्ष") == 60
    assert parse_indian_number("18") == 18


def test_percentage_parsing():
    val, unit = parse_percentage("40 प्रतिशत")
    assert val == 40.0
    assert unit == "PERCENT"

    val_en, unit_en = parse_percentage("40%")
    assert val_en == 40.0

    val_hi_digit, _ = parse_percentage("४० प्रतिशत")
    assert val_hi_digit == 40.0


def test_exact_boundary_operators_and_negation():
    # 60 वर्ष या अधिक -> GTE 60
    op, val, unit = detect_operator_and_value("60 वर्ष या अधिक")
    assert op == OperatorEnum.GTE
    assert val == 60
    assert unit == "years"

    # 60 वर्ष पूर्ण कर चुके -> GTE 60
    op, val, _ = detect_operator_and_value("60 वर्ष पूर्ण कर चुके")
    assert op == OperatorEnum.GTE
    assert val == 60

    # कम से कम 60 वर्ष -> GTE 60
    op, val, _ = detect_operator_and_value("कम से कम 60 वर्ष")
    assert op == OperatorEnum.GTE
    assert val == 60

    # 60 वर्ष से अधिक -> GT 60
    op, val, _ = detect_operator_and_value("60 वर्ष से अधिक")
    assert op == OperatorEnum.GT
    assert val == 60

    # 60 वर्ष से कम -> LT 60
    op, val, _ = detect_operator_and_value("60 वर्ष से कम")
    assert op == OperatorEnum.LT
    assert val == 60

    # 60 वर्ष तक -> LTE 60
    op, val, _ = detect_operator_and_value("60 वर्ष तक")
    assert op == OperatorEnum.LTE
    assert val == 60

    # Hindi Negation: 60 वर्ष से अधिक नहीं -> LTE 60
    op, val, _ = detect_operator_and_value("60 वर्ष से अधिक नहीं")
    assert op == OperatorEnum.LTE
    assert val == 60

    # Hindi Negation: आय ₹2 लाख से अधिक नहीं होनी चाहिए -> LTE 200000
    op, val, _ = detect_operator_and_value("आय ₹2 लाख से अधिक नहीं होनी चाहिए")
    assert op == OperatorEnum.LTE
    assert val == 200000

    # Hindi Negation: 60 वर्ष से कम नहीं -> GTE 60
    op, val, _ = detect_operator_and_value("60 वर्ष से कम नहीं")
    assert op == OperatorEnum.GTE
    assert val == 60

    # Between range: 18 से 40 वर्ष -> BETWEEN [18, 40]
    op, val, _ = detect_operator_and_value("18 से 40 वर्ष")
    assert op == OperatorEnum.BETWEEN
    assert val == [18, 40]


def test_date_and_duration_parsing():
    # Indian DD/MM/YYYY
    d1 = parse_date_expression("31/03/2026")
    assert d1["date_type"] == "EXACT"
    assert d1["normalized_date"] == "2026-03-31"

    # Indian DD-MM-YYYY
    d2 = parse_date_expression("31-03-2026")
    assert d2["date_type"] == "EXACT"
    assert d2["normalized_date"] == "2026-03-31"

    # ISO YYYY-MM-DD
    d3 = parse_date_expression("2026-03-31")
    assert d3["date_type"] == "EXACT"
    assert d3["normalized_date"] == "2026-03-31"

    # Relative duration: within 30 days
    d4 = parse_date_expression("within 30 days of notification")
    assert d4["date_type"] == "RELATIVE_DURATION"
    assert d4["relative_duration"] == {"value": 30, "unit": "days"}

    # Relative duration: 30 दिन के भीतर
    d5 = parse_date_expression("30 दिन के भीतर")
    assert d5["date_type"] == "RELATIVE_DURATION"
    assert d5["relative_duration"] == {"value": 30, "unit": "days"}


def test_currency_and_periodicity_detection():
    assert detect_currency("₹ 1,000") == "INR"
    assert detect_currency("रुपये 5000") == "INR"
    assert detect_currency("Rs. 2000") == "INR"

    assert detect_periodicity("प्रति माह ₹1000") == PeriodicityEnum.MONTHLY
    assert detect_periodicity("वार्षिक सहायता") == PeriodicityEnum.ANNUAL
    assert detect_periodicity("एकमुश्त राशि") == PeriodicityEnum.ONE_TIME


def test_benefit_normalization_without_invention():
    # Mentioning amount and frequency
    b1 = normalize_benefit(
        raw_text="मासिक पेंशन ₹1,000",
        raw_amount="1000",
        frequency_text="प्रति माह",
        description="वृद्धावस्था पेंशन",
        benefit_type_hint="pension",
        evidence_refs=["EVID-001"],
        benefit_id="BEN-001",
    )
    assert b1.type == BenefitTypeEnum.PENSION
    assert b1.amount == 1000.0
    assert b1.frequency == PeriodicityEnum.MONTHLY
    assert b1.currency == "INR"
    assert b1.evidence_refs == ["EVID-001"]

    # Benefit with NO amount stated -> amount must remain None, NEVER invented!
    b2 = normalize_benefit(
        raw_text="पात्र परिवारों को आर्थिक सहायता दी जाएगी",
        raw_amount=None,
        frequency_text=None,
        description="वित्तीय सहायता",
        benefit_type_hint="cash",
        evidence_refs=["EVID-002"],
        benefit_id="BEN-002",
    )
    assert b2.type == BenefitTypeEnum.CASH
    assert b2.amount is None  # Never invented!
    assert b2.raw_text == "पात्र परिवारों को आर्थिक सहायता दी जाएगी"


def test_required_document_normalization():
    d1 = normalize_document_requirement(
        name_raw="जन आधार कार्ड",
        mandatory_stated=True,
        notes="पहचान व निवास हेतु",
        evidence_refs=["EVID-003"],
        doc_id="DOC-REQ-001",
    )
    assert d1.document_type == DocumentTypeEnum.JAN_AADHAAR
    assert d1.mandatory is True
    assert d1.name_raw == "जन आधार कार्ड"

    # When mandatory is unstated, do NOT assume True
    d2 = normalize_document_requirement(
        name_raw="आय प्रमाण पत्र",
        mandatory_stated=None,
        notes=None,
        evidence_refs=["EVID-004"],
        doc_id="DOC-REQ-002",
    )
    assert d2.document_type == DocumentTypeEnum.INCOME_CERTIFICATE
    assert d2.mandatory is None
