from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    data_type: str  # "integer", "decimal", "string", "boolean", "list"
    display_name_en: str
    display_name_hi: str
    allowed_operators: Set[str] = field(default_factory=set)
    default_unit: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None


FIELD_DEFINITIONS: List[FieldDefinition] = [
    FieldDefinition(
        name="age",
        data_type="integer",
        display_name_en="Age",
        display_name_hi="आयु",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="years",
        min_value=Decimal("0"),
        max_value=Decimal("130"),
    ),
    FieldDefinition(
        name="state",
        data_type="string",
        display_name_en="State of Residence",
        display_name_hi="निवास का राज्य",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="district",
        data_type="string",
        display_name_en="District",
        display_name_hi="ज़िला",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="domicile_status",
        data_type="string",
        display_name_en="Domicile / Mool Niwas",
        display_name_hi="मूल निवास स्थिति",
        allowed_operators={"EQ", "NE", "IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="rural_urban",
        data_type="string",
        display_name_en="Location Type (Rural/Urban)",
        display_name_hi="स्थान प्रकार (ग्रामीण/शहरी)",
        allowed_operators={"EQ", "NE", "IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="gender",
        data_type="string",
        display_name_en="Gender",
        display_name_hi="लिंग",
        allowed_operators={"EQ", "NE", "IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="occupation",
        data_type="string",
        display_name_en="Occupation",
        display_name_hi="व्यवसाय",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="farmer_status",
        data_type="boolean",
        display_name_en="Farmer Status",
        display_name_hi="कृषक स्थिति",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="annual_income",
        data_type="decimal",
        display_name_en="Annual Personal Income",
        display_name_hi="वार्षिक व्यक्तिगत आय",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="INR",
        min_value=Decimal("0"),
    ),
    FieldDefinition(
        name="family_income",
        data_type="decimal",
        display_name_en="Annual Family Income",
        display_name_hi="वार्षिक पारिवारिक आय",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="INR",
        min_value=Decimal("0"),
    ),
    FieldDefinition(
        name="social_category",
        data_type="string",
        display_name_en="Social Category (Caste)",
        display_name_hi="सामाजिक श्रेणी (जाति)",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="bpl_status",
        data_type="boolean",
        display_name_en="BPL Status",
        display_name_hi="बीपीएल स्थिति",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="disability_status",
        data_type="boolean",
        display_name_en="Disability Status",
        display_name_hi="दिव्यांगता स्थिति",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="disability_percentage",
        data_type="decimal",
        display_name_en="Disability Percentage",
        display_name_hi="दिव्यांगता प्रतिशत",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="PERCENT",
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    ),
    FieldDefinition(
        name="student_status",
        data_type="boolean",
        display_name_en="Student Status",
        display_name_hi="विद्यार्थी स्थिति",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="education_level",
        data_type="string",
        display_name_en="Education Level",
        display_name_hi="शिक्षा का स्तर",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="marks_percentage",
        data_type="decimal",
        display_name_en="Marks Percentage",
        display_name_hi="प्राप्तांक प्रतिशत",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="PERCENT",
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    ),
    FieldDefinition(
        name="institution_type",
        data_type="string",
        display_name_en="Institution Type",
        display_name_hi="संस्थान का प्रकार",
        allowed_operators={"EQ", "NE", "IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="marital_status",
        data_type="string",
        display_name_en="Marital Status",
        display_name_hi="वैवाहिक स्थिति",
        allowed_operators={"EQ", "NE", "IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="widow_status",
        data_type="boolean",
        display_name_en="Widow Status",
        display_name_hi="विधवा स्थिति",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="land_holding",
        data_type="decimal",
        display_name_en="Land Holding",
        display_name_hi="भूमि स्वामित्व",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        default_unit="hectares",
        min_value=Decimal("0"),
    ),
    FieldDefinition(
        name="family_size",
        data_type="integer",
        display_name_en="Family Size",
        display_name_hi="परिवार के सदस्यों की संख्या",
        allowed_operators={"EQ", "NE", "GT", "GTE", "LT", "LTE", "BETWEEN", "EXISTS", "NOT_EXISTS"},
        min_value=Decimal("1"),
    ),
    FieldDefinition(
        name="existing_scheme_benefits",
        data_type="list",
        display_name_en="Existing Scheme Benefits",
        display_name_hi="वर्तमान में प्राप्त योजनाएं",
        allowed_operators={"IN", "NOT_IN", "EXISTS", "NOT_EXISTS"},
    ),
    FieldDefinition(
        name="pension_status",
        data_type="boolean",
        display_name_en="Receiving Any Pension",
        display_name_hi="पेंशन प्राप्तकर्ता",
        allowed_operators={"EQ", "NE", "EXISTS", "NOT_EXISTS"},
    ),
]

_FIELD_REGISTRY: Dict[str, FieldDefinition] = {f.name: f for f in FIELD_DEFINITIONS}


def get_field_definition(field_name: str) -> Optional[FieldDefinition]:
    """Retrieve field metadata by canonical field name."""
    return _FIELD_REGISTRY.get(field_name.lower().strip())


def is_registered_field(field_name: str) -> bool:
    """Check if field is in canonical field registry."""
    return field_name.lower().strip() in _FIELD_REGISTRY
