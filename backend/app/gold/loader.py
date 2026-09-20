"""
YojanSetu - Day 28: Gold Benchmark Dataset Loader.

Provides task, split, and status-based dataset loading with
strict data-leakage protection (stripping expected labels for runtime evaluation).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.gold.schemas import (
    CaseStatus,
    ConversationGoldCase,
    EligibilityGoldCase,
    ExtractionGoldCase,
    GoldDatasetManifest,
    GoldSplit,
    GoldTask,
    SearchGoldCase,
    VoiceGoldCase,
)

logger = logging.getLogger(__name__)


class GoldBenchmarkLoader:
    """
    Standard loader for the YojanSetu Gold-Standard Evaluation Dataset.
    """

    def __init__(self, dataset_root: Optional[Union[str, Path]] = None, version: str = "v1"):
        if dataset_root:
            self.dataset_dir = Path(dataset_root)
        else:
            # Default to benchmarks/gold/<version> relative to workspace
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            cand1 = repo_root / "benchmarks" / "gold" / version
            major_ver = "v" + version.lstrip("v").split(".")[0]
            cand2 = repo_root / "benchmarks" / "gold" / major_ver
            if cand1.exists():
                self.dataset_dir = cand1
            elif cand2.exists():
                self.dataset_dir = cand2
            else:
                self.dataset_dir = cand1

        self.manifest_path = self.dataset_dir / "manifest.json"

    def load_manifest(self) -> GoldDatasetManifest:
        """Loads and parses the master GoldDatasetManifest."""
        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Gold dataset manifest not found at '{self.manifest_path}'")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GoldDatasetManifest(**data)

    def load_cases(
        self,
        task: Optional[Union[GoldTask, str]] = None,
        split: Optional[Union[GoldSplit, str]] = None,
        status: Optional[Union[CaseStatus, str]] = CaseStatus.HUMAN_VERIFIED,
    ) -> List[Union[ExtractionGoldCase, EligibilityGoldCase, SearchGoldCase, VoiceGoldCase, ConversationGoldCase]]:
        """
        Loads gold cases, optionally filtered by task, split, and status.
        Only HUMAN_VERIFIED cases are returned by default.
        """
        if isinstance(task, str):
            task = GoldTask(task)
        if isinstance(split, str):
            split = GoldSplit(split)
        if isinstance(status, str):
            status = CaseStatus(status)

        manifest = self.load_manifest()
        results = []

        for entry in manifest.cases:
            if task is not None and entry.task != task:
                continue
            if split is not None and entry.split != split:
                continue
            if status is not None and entry.status != status:
                continue

            case_file = self.dataset_dir / entry.relative_path
            if not case_file.is_file():
                logger.warning(f"Referenced case file '{case_file}' not found.")
                continue

            with open(case_file, "r", encoding="utf-8") as f:
                case_data = json.load(f)

            parsed_case = self._parse_case(entry.task, case_data)
            results.append(parsed_case)

        return results

    def _parse_case(self, task: GoldTask, data: Dict[str, Any]):
        if task == GoldTask.EXTRACTION:
            return ExtractionGoldCase(**data)
        elif task == GoldTask.ELIGIBILITY:
            return EligibilityGoldCase(**data)
        elif task == GoldTask.SEARCH:
            return SearchGoldCase(**data)
        elif task == GoldTask.VOICE:
            return VoiceGoldCase(**data)
        elif task == GoldTask.CONVERSATION:
            return ConversationGoldCase(**data)
        else:
            raise ValueError(f"Unknown task '{task}'")

    def get_runtime_inputs(
        self,
        task: Union[GoldTask, str],
        split: Union[GoldSplit, str] = GoldSplit.TEST,
        status: CaseStatus = CaseStatus.HUMAN_VERIFIED,
    ) -> List[Dict[str, Any]]:
        """
        DATA-LEAKAGE PROTECTION:
        Returns pure input fixtures for evaluators with all expected ground-truth
        answers and target labels stripped away.
        """
        cases = self.load_cases(task=task, split=split, status=status)
        runtime_inputs = []

        for c in cases:
            if c.task == GoldTask.EXTRACTION:
                runtime_inputs.append({
                    "case_id": c.case_id,
                    "source": c.source.model_dump(),
                    "difficulty": c.difficulty.value,
                    "tags": c.tags,
                })
            elif c.task == GoldTask.ELIGIBILITY:
                runtime_inputs.append({
                    "case_id": c.case_id,
                    "scheme_version_id": c.scheme_version_id,
                    "evaluation_date": c.evaluation_date,
                    "profile": c.profile,
                    "difficulty": c.difficulty.value,
                    "tags": c.tags,
                })
            elif c.task == GoldTask.SEARCH:
                runtime_inputs.append({
                    "case_id": c.case_id,
                    "query": c.query,
                    "language": c.language,
                    "query_type": c.query_type,
                    "profile": c.profile,
                    "difficulty": c.difficulty.value,
                    "tags": c.tags,
                })
            elif c.task == GoldTask.VOICE:
                runtime_inputs.append({
                    "case_id": c.case_id,
                    "audio_file": c.audio_file,
                    "context": c.context.model_dump(),
                    "difficulty": c.difficulty.value,
                    "tags": c.tags,
                })
            elif c.task == GoldTask.CONVERSATION:
                # Return dialogue prompts without expected future states/actions
                runtime_inputs.append({
                    "case_id": c.case_id,
                    "conversation_id": c.conversation_id,
                    "language": c.language,
                    "description": c.description,
                    "user_inputs": [t.user_text for t in c.turns],
                })

        return runtime_inputs
