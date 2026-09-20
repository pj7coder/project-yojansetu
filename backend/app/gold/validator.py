"""
JanSetu - Day 28: Gold Dataset Master Validator.

Validates schema constraints, ID uniqueness, split integrity, tri-state
eligibility logic, evidence existence, audio hashes, and citizen privacy.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.gold.evidence_validator import GoldEvidenceValidator
from app.gold.schemas import (
    CaseStatus,
    ConversationGoldCase,
    EligibilityGoldCase,
    EligibilityStatus,
    ExtractionGoldCase,
    GoldCaseMeta,
    GoldDatasetManifest,
    GoldSplit,
    GoldTask,
    SearchGoldCase,
    VoiceGoldCase,
)

logger = logging.getLogger(__name__)

# Patterns for catching accidental citizen PII in synthetic profiles
AADHAAR_REGEX = re.compile(r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b")
PHONE_REGEX = re.compile(r"\b(?:\+?91[\-\s]?)?[6789]\d{9}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")


class GoldDatasetValidator:
    """
    Master validator for JanSetu Gold-Standard Evaluation Datasets.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None):
        self.evidence_validator = GoldEvidenceValidator(workspace_root)
        self.seen_case_ids: Set[str] = set()

    def reset(self):
        self.seen_case_ids.clear()

    def check_pii(self, obj: Any, case_id: str) -> List[str]:
        """
        Recursively scans strings in dictionaries or lists for potential
        Aadhaar numbers, 10-digit mobile numbers, or email addresses.
        """
        errors = []
        if isinstance(obj, str):
            # Check Aadhaar (12 digits, doesn't start with 0 or 1)
            # Exclude round monetary amounts (e.g. 100000) or short strings
            if len(obj) >= 12 and AADHAAR_REGEX.search(obj):
                # Don't trigger on dummy/test strings like '000000000000'
                errors.append(f"Case '{case_id}': Potential Aadhaar number detected in field value: '{obj}'")
            if PHONE_REGEX.search(obj):
                errors.append(f"Case '{case_id}': Potential phone number detected in field value: '{obj}'")
            if EMAIL_REGEX.search(obj):
                errors.append(f"Case '{case_id}': Potential email address detected in field value: '{obj}'")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                # Check for explicit PII keys that shouldn't be populated with real data
                if str(k).lower() in ("aadhaar", "phone", "mobile", "email", "pan_card"):
                    if v and str(v).strip() and not str(v).startswith("SYNTHETIC"):
                        errors.append(f"Case '{case_id}': Explicit PII key '{k}' contains value '{v}'.")
                errors.extend(self.check_pii(v, case_id))
        elif isinstance(obj, list):
            for item in obj:
                errors.extend(self.check_pii(item, case_id))
        return errors

    def validate_case_meta(self, case: GoldCaseMeta) -> List[str]:
        """Validates base metadata common to all gold cases."""
        errors = []

        # 1. Unique Case ID
        if case.case_id in self.seen_case_ids:
            errors.append(f"Duplicate case_id '{case.case_id}' detected!")
        else:
            self.seen_case_ids.add(case.case_id)

        # 2. Valid Split
        if case.split not in (GoldSplit.DEV, GoldSplit.VALIDATION, GoldSplit.TEST):
            errors.append(f"Case '{case.case_id}': Invalid split '{case.split}'.")

        # 3. Valid Status
        if case.status not in CaseStatus:
            errors.append(f"Case '{case.case_id}': Invalid status '{case.status}'.")

        # 4. Valid Task
        if case.task not in GoldTask:
            errors.append(f"Case '{case.case_id}': Invalid task '{case.task}'.")

        return errors

    def validate_extraction_case(self, case: ExtractionGoldCase) -> List[str]:
        """Validates an extraction gold case."""
        errors = self.validate_case_meta(case)
        errors.extend(self.evidence_validator.validate_extraction_evidence(case))
        errors.extend(self.check_pii(case.model_dump(), case.case_id))
        return errors

    def validate_eligibility_case(self, case: EligibilityGoldCase) -> List[str]:
        """Validates an eligibility gold case."""
        errors = self.validate_case_meta(case)

        # Tri-state status check
        if case.expected.status not in (
            EligibilityStatus.ELIGIBLE,
            EligibilityStatus.NOT_ELIGIBLE,
            EligibilityStatus.MORE_INFORMATION_REQUIRED,
        ):
            errors.append(f"Case '{case.case_id}': Status '{case.expected.status}' violates tri-state contract.")

        # Check PII in synthetic citizen profile
        errors.extend(self.check_pii(case.profile, case.case_id))

        # Check evidence and scheme version
        errors.extend(self.evidence_validator.validate_eligibility_evidence(case))
        return errors

    def validate_search_case(self, case: SearchGoldCase) -> List[str]:
        """Validates a search gold case."""
        errors = self.validate_case_meta(case)
        if not case.query and case.query_type != "NO_QUERY":
            errors.append(f"Case '{case.case_id}': Missing query text for query_type '{case.query_type}'.")
        if case.profile:
            errors.extend(self.check_pii(case.profile, case.case_id))
        return errors

    def validate_voice_case(self, case: VoiceGoldCase) -> List[str]:
        """Validates a voice gold case."""
        errors = self.validate_case_meta(case)
        errors.extend(self.evidence_validator.validate_voice_evidence(case))
        errors.extend(self.check_pii(case.model_dump(), case.case_id))
        return errors

    def validate_conversation_case(self, case: ConversationGoldCase) -> List[str]:
        """Validates a scripted multi-turn conversation case."""
        errors = self.validate_case_meta(case)
        if not case.turns:
            errors.append(f"Case '{case.case_id}': Conversation has no turns.")
        for t in case.turns:
            if not t.expected_state:
                errors.append(f"Case '{case.case_id}' turn {t.turn_index}: Missing expected_state.")
            if not t.expected_action:
                errors.append(f"Case '{case.case_id}' turn {t.turn_index}: Missing expected_action.")
        return errors

    def validate_manifest(
        self,
        manifest: GoldDatasetManifest,
        all_cases: List[Union[ExtractionGoldCase, EligibilityGoldCase, SearchGoldCase, VoiceGoldCase, ConversationGoldCase]],
    ) -> List[str]:
        """Validates top-level manifest consistency against loaded cases."""
        errors = []
        actual_total = len(all_cases)
        manifest_cases_count = len(manifest.cases)

        if actual_total != manifest_cases_count:
            errors.append(
                f"Manifest case count mismatch: manifest lists {manifest_cases_count} cases, "
                f"but loaded {actual_total} cases."
            )

        # Validate task counts
        task_counts: Dict[str, int] = {}
        split_counts: Dict[str, Dict[str, int]] = {}

        for c in all_cases:
            t = c.task.value
            s = c.split.value
            task_counts[t] = task_counts.get(t, 0) + 1

            if t not in split_counts:
                split_counts[t] = {}
            split_counts[t][s] = split_counts[t].get(s, 0) + 1

        for task_name, expected_count in manifest.task_counts.items():
            act = task_counts.get(task_name, 0)
            if act != expected_count:
                errors.append(
                    f"Manifest task count mismatch for '{task_name}': manifest={expected_count}, actual={act}"
                )

        return errors
