import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from app.normalization.schemas import SchemeOriginEnum
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext

_DISTRICTS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _load_districts_registry() -> Dict[str, Dict[str, Any]]:
    global _DISTRICTS_CACHE
    if _DISTRICTS_CACHE is not None:
        return _DISTRICTS_CACHE

    reg_path = Path(__file__).resolve().parent.parent.parent / "reference_data" / "rajasthan_districts.json"
    districts_map: Dict[str, Dict[str, Any]] = {}

    if reg_path.exists():
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("districts", []):
                # Map standard name
                districts_map[d["name"].lower().strip()] = d
                # Map Hindi name
                if "name_hi" in d:
                    districts_map[d["name_hi"].lower().strip()] = d
                # Map aliases
                for alias in d.get("aliases", []):
                    districts_map[alias.lower().strip()] = d
        except Exception:
            pass

    _DISTRICTS_CACHE = districts_map
    return _DISTRICTS_CACHE


class GeographyValidator(BaseValidator):
    """
    Validates Rajasthan districts against local reference registry,
    verifies state jurisdiction consistency, and validates scheme origin.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft
        districts_registry = _load_districts_registry()

        # 1. District validation
        if draft.scope and draft.scope.districts:
            for idx, district_name in enumerate(draft.scope.districts):
                context.increment_rules_checked(1)
                cleaned = str(district_name).lower().strip()
                field_path = f"scope.districts[{idx}]"

                if cleaned not in districts_registry:
                    context.add_issue(
                        rule_code="DISTRICT_UNKNOWN",
                        message=f"District '{district_name}' is not recognized in the Rajasthan district reference dataset.",
                        field_path=field_path,
                        actual_value=district_name,
                        severity=ValidationSeverity.ERROR,
                    )
                else:
                    d_record = districts_registry[cleaned]
                    if d_record.get("status") == "HISTORICAL":
                        context.add_issue(
                            rule_code="DISTRICT_REVIEW_REQUIRED",
                            message=f"District '{district_name}' is marked as historical/reorganized; review required.",
                            field_path=field_path,
                            actual_value=district_name,
                            severity=ValidationSeverity.WARNING,
                        )

        # 2. State consistency
        if draft.scope and draft.scope.state:
            context.increment_rules_checked(1)
            state_cleaned = draft.scope.state.strip().lower()
            valid_states = {"rajasthan", "राजस्थान"}
            if state_cleaned not in valid_states:
                context.add_issue(
                    rule_code="STATE_CONFLICT",
                    message=f"Draft scope specifies state '{draft.scope.state}', which is outside Rajasthan jurisdiction.",
                    field_path="scope.state",
                    actual_value=draft.scope.state,
                    severity=ValidationSeverity.WARNING,
                )

        # 3. Scheme Origin
        if draft.scheme_identity:
            context.increment_rules_checked(1)
            origin = draft.scheme_identity.scheme_origin
            if not isinstance(origin, SchemeOriginEnum):
                context.add_issue(
                    rule_code="SCHEME_ORIGIN_INVALID",
                    message=f"Unrecognized scheme origin '{origin}'.",
                    field_path="scheme_identity.scheme_origin",
                    actual_value=str(origin),
                    severity=ValidationSeverity.ERROR,
                )
