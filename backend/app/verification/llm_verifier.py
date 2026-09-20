import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.llm import (
    BaseLLMProvider,
    LLMSchemaValidationError,
    LLMUnavailableError,
    MockLLMProvider,
    OllamaProvider,
)
from app.llm.interface import LLMResponseMetadata
from app.verification.schemas import (
    LLMVerificationResponse,
    VerifiableFact,
    VerificationReasonCode,
    VerificationResult,
)

logger = logging.getLogger("jansetu.verification.llm")


class LLMEvidenceVerifier:
    """
    Second-pass LLM verifier powered by local Llama 3.2 3B via BaseLLMProvider.
    Evaluates individual atomic claims against sandboxed government source evidence.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        prompt_path: Optional[Path] = None,
    ):
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif settings.llm_provider.lower() == "mock":
            self.llm_provider = MockLLMProvider()
        else:
            self.llm_provider = OllamaProvider()

        self.prompt_version = settings.evidence_verification_prompt_version
        self.schema_version = settings.evidence_verification_schema_version
        self.max_retries = settings.evidence_verifier_max_retries

        if prompt_path is None:
            prompt_path = (
                Path(__file__).parent / "prompts" / "evidence_verifier_v1.txt"
            )

        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        else:
            logger.warning(f"Prompt template not found at {prompt_path}, using fallback.")
            self.system_prompt = "Verify the fact strictly against the provided government source evidence. Return SUPPORTED, CONTRADICTED, or NOT_ENOUGH_EVIDENCE."

    def build_verification_prompt(
        self,
        fact: VerifiableFact,
        sandboxed_evidence: str,
    ) -> str:
        """Constructs safe, structured prompt for a single atomic fact."""
        canon_val_str = (
            json.dumps(fact.canonical_value, ensure_ascii=False)
            if fact.canonical_value
            else "None"
        )
        table_info = (
            f"\nTable Context: {fact.table_context}"
            if fact.table_context
            else ""
        )

        return (
            f"=== FACT TO VERIFY ===\n"
            f"Fact ID: {fact.fact_id}\n"
            f"Field Path: {fact.field_path}\n"
            f"Fact Type: {fact.fact_type.value}\n"
            f"Risk Level: {fact.risk_level.value}\n"
            f"Claim Statement: {fact.statement}\n"
            f"Canonical Value: {canon_val_str}"
            f"{table_info}\n\n"
            f"=== SOURCE EVIDENCE ===\n"
            f"{sandboxed_evidence}\n\n"
            f"Verify whether the source evidence supports, contradicts, or has insufficient evidence for the claim."
        )

    def verify_fact(
        self,
        fact: VerifiableFact,
        sandboxed_evidence: str,
    ) -> Tuple[Optional[LLMVerificationResponse], Optional[LLMResponseMetadata], Optional[str]]:
        """
        Executes zero-temperature structured inference against Ollama / Llama.

        Returns:
            Tuple of (LLMVerificationResponse, LLMResponseMetadata, error_message)
        """
        prompt = self.build_verification_prompt(fact, sandboxed_evidence)
        options = {
            "temperature": 0.0,
            "num_predict": 256,
        }

        last_error = None
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.llm_provider.generate_structured(
                    prompt=prompt,
                    schema=LLMVerificationResponse,
                    system_prompt=self.system_prompt,
                    options=options,
                )
                data: LLMVerificationResponse = response.data
                return data, response.metadata, None

            except LLMSchemaValidationError as sve:
                last_error = f"Schema validation error: {sve}"
                logger.warning(
                    f"Fact {fact.fact_id} verification attempt {attempt} failed schema validation: {sve}"
                )
                if attempt > self.max_retries:
                    break

            except LLMUnavailableError as ue:
                logger.error(f"LLM service unavailable during fact verification: {ue}")
                return None, None, f"LLM unavailable: {ue}"

            except Exception as ex:
                logger.error(f"Unexpected error during fact verification: {ex}")
                return None, None, f"Inference error: {ex}"

        return None, None, last_error or "Exhausted retries"
