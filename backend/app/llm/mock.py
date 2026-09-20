from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from app.llm.interface import (
    BaseLLMProvider,
    LLMResponseMetadata,
    LLMSchemaValidationError,
    LLMUnavailableError,
    StructuredLLMResponse,
)

logger = logging.getLogger("yojansetu.llm.mock")

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for unit tests, offline development, and CI.
    Simulates exact model responses, token counts, and failure conditions without requiring Ollama.
    """

    def __init__(
        self,
        default_response_dict: Optional[Dict[str, Any]] = None,
        response_factory: Optional[Callable[[str, Type[Any]], Dict[str, Any]]] = None,
        simulate_unavailable: bool = False,
        simulate_malformed_json: bool = False,
        simulate_schema_error: bool = False,
        model_name: str = "mock-llama3.2:3b",
    ):
        self.default_response_dict = default_response_dict or {}
        self.response_factory = response_factory
        self.simulate_unavailable = simulate_unavailable
        self.simulate_malformed_json = simulate_malformed_json
        self.simulate_schema_error = simulate_schema_error
        self.model_name = model_name
        self.call_count = 0
        self.last_prompt = ""
        self.last_system_prompt = ""

    def check_health(self) -> Dict[str, Any]:
        if self.simulate_unavailable:
            return {
                "status": "error",
                "provider": "mock",
                "model_available": False,
                "error": "Simulated mock Ollama server unavailable.",
            }
        return {
            "status": "ok",
            "provider": "mock",
            "model": self.model_name,
            "model_available": True,
            "installed_models": [self.model_name],
        }

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> StructuredLLMResponse:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt or ""

        if self.simulate_unavailable:
            raise LLMUnavailableError("Mock provider simulated: Ollama server is offline or unreachable.")

        if self.simulate_malformed_json:
            raise LLMSchemaValidationError(
                "Malformed JSON in simulated model output",
                raw_response="{\"schemes\": [broken_json...",
            )

        if self.simulate_schema_error:
            raise LLMSchemaValidationError(
                "Simulated schema validation failure: required field 'schema_version' missing",
                raw_response="{\"invalid_field\": true}",
            )

        # Generate response data dict
        if self.response_factory:
            data_dict = self.response_factory(prompt, schema)
        elif self.default_response_dict:
            data_dict = self.default_response_dict
        elif getattr(schema, "__name__", "") == "LLMVerificationResponse":
            data_dict = {
                "result": "SUPPORTED",
                "reason_code": "DIRECT_MATCH",
                "explanation": "Default mock verified match.",
            }
        else:
            # Fallback empty structure matching schema
            data_dict = {
                "schema_version": "1.0",
                "document_id": "test-doc",
                "chunk_id": "test-chunk",
                "section_type": "GENERAL",
                "schemes": [],
            }

        raw_json_str = json.dumps(data_dict, ensure_ascii=False)
        metadata = LLMResponseMetadata(
            provider="mock",
            model_name=self.model_name,
            raw_response=raw_json_str,
            duration_ms=45,
            input_tokens=len(prompt.split()) * 2,
            output_tokens=len(raw_json_str.split()) * 2,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        try:
            instance = schema.model_validate(data_dict)
            return StructuredLLMResponse(data=instance, metadata=metadata)
        except ValidationError as e:
            raise LLMSchemaValidationError(f"Mock validation failed: {e}", raw_response=raw_json_str) from e
