from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.llm.interface import (
    BaseLLMProvider,
    LLMProviderError,
    LLMResponseMetadata,
    LLMSchemaValidationError,
    LLMUnavailableError,
    StructuredLLMResponse,
)

logger = logging.getLogger("yojansetu.llm.ollama")

T = TypeVar("T", bound=BaseModel)


class OllamaProvider(BaseLLMProvider):
    """
    Local offline LLM provider communicating with Ollama server via HTTP REST API.
    Enforces deterministic JSON extraction using Llama 3.2.
    """

    _cached_health: Optional[Dict[str, Any]] = None
    _cached_health_ts: float = 0.0
    HEALTH_CACHE_TTL: float = 15.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        raw_url = (base_url or settings.ollama_base_url).rstrip("/")
        # Windows IPv6 fix: map localhost to 127.0.0.1 to avoid 2-second DNS stall
        if "://localhost" in raw_url:
            raw_url = raw_url.replace("://localhost", "://127.0.0.1")
        self.base_url = raw_url
        self.model_name = model_name or settings.ollama_model
        self.timeout_seconds = timeout_seconds or settings.llm_request_timeout_seconds

    def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Verify Ollama daemon is reachable and the configured model is installed.
        Cached with a short TTL to keep admin panel transitions instantaneous.
        """
        now = time.time()
        if not force_refresh and OllamaProvider._cached_health and (now - OllamaProvider._cached_health_ts) < self.HEALTH_CACHE_TTL:
            return OllamaProvider._cached_health

        url = f"{self.base_url}/api/tags"
        result: Dict[str, Any]
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    result = {
                        "status": "error",
                        "provider": "ollama",
                        "model_available": False,
                        "error": f"Ollama HTTP {resp.status_code}: {resp.text}",
                    }
                else:
                    data = resp.json()
                    models = data.get("models", [])
                    installed_names = [m.get("name", "") for m in models]
                    model_found = any(
                        self.model_name == name or name.startswith(f"{self.model_name}:")
                        for name in installed_names
                    )
                    result = {
                        "status": "ok",
                        "provider": "ollama",
                        "model": self.model_name,
                        "model_available": model_found,
                        "installed_models": installed_names,
                    }
        except httpx.ConnectError:
            result = {
                "status": "error",
                "provider": "ollama",
                "model_available": False,
                "error": f"Cannot connect to Ollama server at {self.base_url}. Ensure Ollama daemon is running.",
            }
        except Exception as exc:
            result = {
                "status": "error",
                "provider": "ollama",
                "model_available": False,
                "error": str(exc),
            }

        OllamaProvider._cached_health = result
        OllamaProvider._cached_health_ts = now
        return result


    @staticmethod
    def _strip_markdown_fencing(text: str) -> str:
        """Strip optional ```json ... ``` markdown code blocks from model response."""
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            return match.group(1).strip()
        return cleaned

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> StructuredLLMResponse:
        """
        Execute deterministic structured extraction through Ollama's /api/generate endpoint.
        """
        url = f"{self.base_url}/api/generate"

        req_options = {
            "temperature": settings.llm_temperature,
            "num_ctx": settings.llm_num_ctx,
        }
        if options:
            req_options.update(options)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": req_options,
        }
        if system_prompt:
            payload["system"] = system_prompt

        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        response = None
        context_candidates = [req_options.get("num_ctx", 2048)]
        if context_candidates[0] > 1536:
            context_candidates.append(1536)
        if context_candidates[-1] > 1024:
            context_candidates.append(1024)

        for ctx in context_candidates:
            payload["options"]["num_ctx"] = ctx
            try:
                with httpx.Client(timeout=float(self.timeout_seconds)) as client:
                    response = client.post(url, json=payload)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                raise LLMUnavailableError(
                    f"Cannot connect to Ollama service at {self.base_url}: {e}"
                ) from e
            except httpx.ReadTimeout as e:
                raise LLMUnavailableError(
                    f"Ollama request timed out after {self.timeout_seconds}s: {e}"
                ) from e
            except Exception as e:
                raise LLMProviderError(f"Unexpected Ollama network error: {e}") from e

            # If success, break loop
            if response.status_code == 200:
                break

            err_body = response.text.lower()
            is_mem_err = "unable to allocate" in err_body or "failed to allocate" in err_body or "out-of-memory" in err_body or "terminated" in err_body
            if is_mem_err and ctx != context_candidates[-1]:
                logger.warning(f"Ollama memory issue with num_ctx={ctx}, retrying with smaller context window...")
                time.sleep(1.0)
                continue

            # Non-recoverable HTTP error
            if is_mem_err:
                raise LLMUnavailableError(
                    f"Ollama model '{self.model_name}' memory allocation failed: {response.text}"
                )
            if "not found" in err_body:
                raise LLMUnavailableError(
                    f"Model '{self.model_name}' not found on Ollama server: {response.text}"
                )
            raise LLMProviderError(
                f"Ollama server returned HTTP {response.status_code}: {response.text}"
            )

        duration_ms = int((time.perf_counter() - t0) * 1000)
        completed_at = datetime.now(timezone.utc)

        try:
            resp_json = response.json()
        except Exception as e:
            raise LLMSchemaValidationError(
                f"Failed to decode Ollama response envelope as JSON: {e}",
                raw_response=response.text,
            ) from e

        raw_content = resp_json.get("response", "")
        cleaned_json_str = self._strip_markdown_fencing(raw_content)

        metadata = LLMResponseMetadata(
            provider="ollama",
            model_name=self.model_name,
            raw_response=raw_content,
            duration_ms=duration_ms,
            input_tokens=resp_json.get("prompt_eval_count"),
            output_tokens=resp_json.get("eval_count"),
            started_at=started_at,
            completed_at=completed_at,
            additional_info={
                "total_duration": resp_json.get("total_duration"),
                "load_duration": resp_json.get("load_duration"),
                "eval_duration": resp_json.get("eval_duration"),
            },
        )

        try:
            parsed_data = json.loads(cleaned_json_str)
            validated_instance = schema.model_validate(parsed_data)
            return StructuredLLMResponse(data=validated_instance, metadata=metadata)
        except json.JSONDecodeError as e:
            logger.warning("Ollama response contained malformed JSON: %s", e)
            raise LLMSchemaValidationError(
                f"Malformed JSON in Ollama response: {e}",
                raw_response=raw_content,
            ) from e
        except ValidationError as e:
            logger.warning("Ollama response failed Pydantic schema validation: %s", e)
            raise LLMSchemaValidationError(
                f"Schema validation failed: {e}",
                raw_response=raw_content,
            ) from e
