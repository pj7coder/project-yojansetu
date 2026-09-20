from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DISTRICTS_CACHE: Optional[Dict[str, str]] = None


def _load_canonical_districts() -> Dict[str, str]:
    """Loads map of lower-cased district aliases/names -> canonical English name."""
    global _DISTRICTS_CACHE
    if _DISTRICTS_CACHE is not None:
        return _DISTRICTS_CACHE

    reg_path = Path(__file__).resolve().parent.parent / "reference_data" / "rajasthan_districts.json"
    districts_map: Dict[str, str] = {}

    if reg_path.exists():
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("districts", []):
                canon_name = d["name"]
                districts_map[canon_name.lower().strip()] = canon_name
                if "name_hi" in d:
                    districts_map[d["name_hi"].lower().strip()] = canon_name
                for alias in d.get("aliases", []):
                    districts_map[alias.lower().strip()] = canon_name
        except Exception:
            pass

    _DISTRICTS_CACHE = districts_map
    return _DISTRICTS_CACHE


class CitizenProfile(BaseModel):
    """
    Typed citizen profile representation for deterministic eligibility evaluation.
    Supports partial profiles (missing fields remain None = UNKNOWN).
    Never persists personal citizen data automatically.
    """
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    # Demographics
    age: Optional[int] = Field(default=None, description="Age in completed years")
    date_of_birth: Optional[date] = Field(default=None, description="Citizen DOB if provided")
    gender: Optional[str] = Field(default=None, description="MALE, FEMALE, OTHER, etc.")
    marital_status: Optional[str] = Field(default=None, description="SINGLE, MARRIED, WIDOWED, DIVORCED")
    widow_status: Optional[bool] = Field(default=None, description="Explicit widow indicator")

    # Geography & Domicile
    state: Optional[str] = Field(default=None, description="Current state of residence")
    district: Optional[str] = Field(default=None, description="District name")
    domicile: Optional[str] = Field(default=None, description="Legal domicile state (e.g. 'Rajasthan')")
    domicile_status: Optional[str] = Field(
        default=None,
        description="Legal domicile state (e.g. 'Rajasthan') or 'YES'/'NO'. Kept strictly distinct from current state."
    )
    rural_urban: Optional[str] = Field(default=None, description="RURAL, URBAN, BOTH")

    # Socio-Economic
    social_category: Optional[str] = Field(default=None, description="SC, ST, OBC, GENERAL, EWS, MBC, etc.")
    bpl_status: Optional[bool] = Field(default=None, description="True if citizen holds BPL status")
    occupation: Optional[str] = Field(default=None, description="Canonical occupation (FARMER, LABOURER, ARTISAN, etc.)")
    farmer_status: Optional[bool] = Field(default=None, description="Explicit farmer status")
    land_holding: Optional[Decimal] = Field(default=None, description="Land holding in hectares or standard unit")
    land_holding_unit: Optional[str] = Field(default="hectares", description="Unit of land holding")

    # Income (strictly segregated)
    annual_income: Optional[Decimal] = Field(default=None, description="Personal annual income in INR")
    annual_income_frequency: Optional[str] = Field(default="ANNUAL", description="ANNUAL or MONTHLY")
    family_income: Optional[Decimal] = Field(default=None, description="Family annual income in INR")
    family_income_frequency: Optional[str] = Field(default="ANNUAL", description="ANNUAL or MONTHLY")
    family_size: Optional[int] = Field(default=None, description="Number of family members")

    # Disability
    disability_status: Optional[bool] = Field(default=None, description="Explicit disability indicator")
    disability_percentage: Optional[Decimal] = Field(default=None, description="Percentage of disability (0-100)")

    # Education
    student_status: Optional[bool] = Field(default=None, description="Explicit student indicator")
    education_level: Optional[str] = Field(default=None, description="PRIMARY, SECONDARY, HIGHER_SECONDARY, GRADUATE, etc.")
    marks_percentage: Optional[Decimal] = Field(default=None, description="Percentage marks obtained")
    institution_type: Optional[str] = Field(default=None, description="GOVERNMENT, PRIVATE, AIDED")

    # Existing benefits / exclusions
    existing_scheme_benefits: List[str] = Field(default_factory=list, description="List of currently active scheme codes")
    pension_status: Optional[bool] = Field(default=None, description="True if citizen already receives any pension")
    receiving_pension_x: Optional[bool] = Field(default=None, description="Specific named pension indicator for exclusion tests")
    is_government_employee: Optional[bool] = Field(default=None, description="True if citizen is a government employee")
    is_income_tax_payer: Optional[bool] = Field(default=None, description="True if citizen is an income tax payer")

    # Extensibility
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom application attributes")

    # --- Validators for impossible inputs ---

    @field_validator("age", mode="before")
    @classmethod
    def validate_age(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid age value: {v}")
        if val < 0 or val > 130:
            raise ValueError(f"Age must be between 0 and 130, got: {val}")
        return val

    @field_validator("annual_income", "family_income", "land_holding", mode="before")
    @classmethod
    def validate_positive_numbers(cls, v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            d = Decimal(str(v).strip().replace(",", ""))
        except Exception:
            raise ValueError(f"Invalid numeric input: {v}")
        if d < 0:
            raise ValueError(f"Income or land holding cannot be negative: {d}")
        return d

    @field_validator("disability_percentage", "marks_percentage", mode="before")
    @classmethod
    def validate_percentage(cls, v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            d = Decimal(str(v).strip().replace("%", "").strip())
        except Exception:
            raise ValueError(f"Invalid percentage input: {v}")
        if d < 0 or d > 100:
            raise ValueError(f"Percentage must be between 0 and 100, got: {d}")
        return d

    @field_validator("family_size", mode="before")
    @classmethod
    def validate_family_size(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        val = int(v)
        if val < 1:
            raise ValueError(f"Family size must be at least 1, got: {val}")
    @model_validator(mode="before")
    @classmethod
    def handle_field_aliases_and_extras(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            custom = dict(d.get("custom_fields") or {})
            for k, v in list(d.items()):
                if k not in cls.model_fields:
                    custom[k] = v
            # Alias mapping
            if "land_area_bigha" in d and "land_holding" not in d:
                d["land_holding"] = d["land_area_bigha"]
            if "caste_category" in d and "social_category" not in d:
                d["social_category"] = d["caste_category"]
            if "is_student" in d and "student_status" not in d:
                d["student_status"] = d["is_student"]
            if "is_bpl" in d and "bpl_status" not in d:
                d["bpl_status"] = d["is_bpl"]
            if "has_jan_aadhaar" in d:
                custom["has_jan_aadhaar"] = d["has_jan_aadhaar"]
            d["custom_fields"] = custom
            return d
        return data

    @model_validator(mode="after")
    def normalize_profile_fields(self) -> "CitizenProfile":
        """
        Deterministic normalizations:
        1. Monthly income -> Annual income (when frequency is explicitly MONTHLY).
        2. District alias resolution via canonical registry.
        3. State canonicalization.
        4. Category / Gender standard upper casing.
        """
        # Income monthly -> annual
        if self.family_income is not None and self.family_income_frequency:
            if self.family_income_frequency.upper() == "MONTHLY":
                self.family_income = self.family_income * Decimal("12")
                self.family_income_frequency = "ANNUAL"

        if self.annual_income is not None and self.annual_income_frequency:
            if self.annual_income_frequency.upper() == "MONTHLY":
                self.annual_income = self.annual_income * Decimal("12")
                self.annual_income_frequency = "ANNUAL"

        # District alias matching
        if self.district:
            districts_map = _load_canonical_districts()
            raw_d = self.district.strip().lower()
            if raw_d in districts_map:
                self.district = districts_map[raw_d]

        # State canonicalization
        if self.state:
            s_clean = self.state.strip()
            if s_clean.lower() == "rajasthan" or s_clean in ("राजस्थान", "raj"):
                self.state = "Rajasthan"

        # Domicile canonicalization and bidirectional sync
        if self.domicile and not self.domicile_status:
            self.domicile_status = self.domicile
        elif self.domicile_status and not self.domicile:
            self.domicile = self.domicile_status

        if self.domicile:
            dom_clean = str(self.domicile).strip()
            if dom_clean.lower() in ("rajasthan", "राजस्थान", "yes", "true", "1"):
                self.domicile = "Rajasthan"
                self.domicile_status = "Rajasthan"
            else:
                self.domicile = dom_clean
                self.domicile_status = dom_clean
        elif self.domicile_status:
            dom_clean = str(self.domicile_status).strip()
            if dom_clean.lower() in ("rajasthan", "राजस्थान", "yes", "true", "1"):
                self.domicile_status = "Rajasthan"
                self.domicile = "Rajasthan"
            else:
                self.domicile_status = dom_clean
                self.domicile = dom_clean

        # Social category
        if self.social_category:
            self.social_category = self.social_category.strip().upper()

        # Gender
        if self.gender:
            g = self.gender.strip().upper()
            if g in ("M", "MALE", "पुरुष"):
                self.gender = "MALE"
            elif g in ("F", "FEMALE", "महिला", "स्त्री"):
                self.gender = "FEMALE"
            else:
                self.gender = g

        # Rural / Urban
        if self.rural_urban:
            ru = self.rural_urban.strip().upper()
            if ru in ("RURAL", "ग्रामीण"):
                self.rural_urban = "RURAL"
            elif ru in ("URBAN", "शहरी"):
                self.rural_urban = "URBAN"
            elif ru in ("BOTH", "दोनों"):
                self.rural_urban = "BOTH"

        return self

    def get_value(self, field_name: str) -> Any:
        """
        Retrieve value by field name with strict attribute separation.
        Returns None if field is missing or unknown.
        """
        f_norm = field_name.strip().lower()
        if f_norm == "domicile":
            val = self.domicile or self.domicile_status or self.custom_fields.get("domicile") or self.custom_fields.get("domicile_status")
            if val is not None:
                return str(val)
            return None
        if f_norm == "domicile_status":
            val = self.domicile_status or self.domicile or self.custom_fields.get("domicile_status") or self.custom_fields.get("domicile")
            if val is not None:
                return str(val)
            return None
        if f_norm in ("land_area_bigha", "land_area", "land_size"):
            return self.land_holding if self.land_holding is not None else self.custom_fields.get(f_norm)
        if f_norm == "caste_category":
            return self.social_category if self.social_category is not None else self.custom_fields.get("caste_category")
        if f_norm in ("marks_percentage_12", "class_12_marks"):
            return self.marks_percentage if self.marks_percentage is not None else self.custom_fields.get(f_norm)
        if f_norm == "has_jan_aadhaar":
            return self.custom_fields.get("has_jan_aadhaar", True)

        if hasattr(self, f_norm):
            val = getattr(self, f_norm)
            if val is not None:
                return val
        if f_norm in self.custom_fields:
            return self.custom_fields[f_norm]
        # Check underscore vs hyphen
        f_alt = f_norm.replace("-", "_")
        if hasattr(self, f_alt):
            val = getattr(self, f_alt)
            if val is not None:
                return val
        if f_alt in self.custom_fields:
            return self.custom_fields[f_alt]
        return None
