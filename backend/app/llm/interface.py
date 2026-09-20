from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMUnavailableError(LLMProviderError):
    """Raised when the LLM service (e.g. Ollama daemon) cannot be reached or model cannot be loaded."""
    pass


class LLMSchemaValidationError(LLMProviderError):
    """Raised when the model response fails JSON parsing or Pydantic schema validation."""
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.raw_response = raw_response


@dataclass
class LLMResponseMetadata:
    """Standardized metadata captured from an LLM inference call."""
    provider: str
    model_name: str
    raw_response: str
    duration_ms: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredLLMResponse:
    """Wrapper containing parsed Pydantic object and underlying call metadata."""
    data: Any
    metadata: LLMResponseMetadata


class BaseLLMProvider(ABC):
    """Abstract interface for local and test LLM inference providers."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> StructuredLLMResponse:
        """
        Execute deterministic structured generation returning an instance of schema T.

        Args:
            prompt: User/chunk text prompt
            schema: Pydantic model class to validate and instantiate
            system_prompt: Optional system-level instructions
            options: Optional inference hyperparameters (temperature, num_ctx, etc.)

        Returns:
            StructuredLLMResponse containing validated instance of T and LLMResponseMetadata
        """
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Verify provider connectivity and model availability.

        Returns:
            Dict containing status ('ok' | 'error'), provider name, and model availability.
        """
        pass
