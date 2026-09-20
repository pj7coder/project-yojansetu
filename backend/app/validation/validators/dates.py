from datetime import datetime
from typing import Dict, List, Optional
from app.normalization.schemas import CanonicalImportantDate
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class DatesValidator(BaseValidator):
    """
    Validates calendar authenticity (e.g. rejects 2026-02-30) and chronological order
    (valid_from <= valid_until, start <= deadline).
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft
        parsed_dates: Dict[str, datetime] = {}

        for idx, dt in enumerate(draft.important_dates):
            context.increment_rules_checked(1)
            field_path = f"important_dates[{idx}].normalized_date"

            if dt.date_type == "EXACT" and dt.normalized_date:
                try:
                    # Strict ISO date validation: YYYY-MM-DD
                    parsed_dt = datetime.strptime(dt.normalized_date, "%Y-%m-%d")
                    event_key = dt.event_name.lower().strip()
                    parsed_dates[event_key] = parsed_dt
                except ValueError as ve:
                    context.add_issue(
                        rule_code="DATE_INVALID",
                        message=f"Date '{dt.normalized_date}' for event '{dt.event_name}' is not a valid calendar date.",
                        field_path=field_path,
                        actual_value=dt.normalized_date,
                        evidence_refs=dt.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )

        # Chronological ordering checks
        context.increment_rules_checked(1)
        valid_from_dt: Optional[datetime] = None
        valid_until_dt: Optional[datetime] = None

        for k, v in parsed_dates.items():
            if "start" in k or "from" in k or "opening" in k or "effective" in k:
                valid_from_dt = v
            elif "end" in k or "until" in k or "deadline" in k or "closing" in k:
                valid_until_dt = v

        if valid_from_dt and valid_until_dt:
            if valid_from_dt > valid_until_dt:
                context.add_issue(
                    rule_code="DATE_RANGE_INVALID",
                    message=f"Effective start date ({valid_from_dt.strftime('%Y-%m-%d')}) chronologically exceeds end date ({valid_until_dt.strftime('%Y-%m-%d')}).",
                    field_path="important_dates",
                    actual_value={
                        "start": valid_from_dt.strftime("%Y-%m-%d"),
                        "end": valid_until_dt.strftime("%Y-%m-%d"),
                    },
                    severity=ValidationSeverity.ERROR,
                )
