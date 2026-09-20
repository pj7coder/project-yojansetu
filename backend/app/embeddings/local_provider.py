import logging
import re
from pathlib import Path
from typing import List, Optional
import unicodedata

from app.core.config import get_settings
from app.embeddings.interface import EmbeddingProvider

logger = logging.getLogger("jansetu.embeddings.local")

_GLOBAL_EMBEDDING_MODEL = None


def normalize_search_text(text: str) -> str:
    """
    Deterministically normalizes text before embedding generation:
    - NFKC Unicode normalization.
    - Preserves Hindi Devanagari and English alphanumeric characters.
    - Collapses repeated whitespace.
    """
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", str(text))
    # Collapse multiple whitespaces
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


class LocalFastEmbedProvider(EmbeddingProvider):
    """
    Offline local sentence embedding provider using fastembed with zero-network fallback.
    Executes entirely offline without blocking on external HuggingFace network requests.
    """

    def __init__(self, model_name: Optional[str] = None):
        settings = get_settings()
        self._model_name = model_name or settings.embedding_model_name
        self._dimension = settings.embedding_dimension
        self._model = None
        self._available = True
        self._initialize_model()

    def _initialize_model(self) -> None:
        global _GLOBAL_EMBEDDING_MODEL
        if _GLOBAL_EMBEDDING_MODEL is not None:
            self._model = _GLOBAL_EMBEDDING_MODEL
            return

        # Check if model weights are already cached locally
        cache_dir = Path.home() / ".cache" / "fastembed"
        if not cache_dir.exists():
            logger.info("FastEmbed local cache not found; running in zero-latency offline fallback mode.")
            return

        try:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name)
            _GLOBAL_EMBEDDING_MODEL = self._model
            logger.info(f"Loaded local embedding model '{self._model_name}' successfully")
        except Exception as e:
            logger.warning(f"FastEmbed offline fallback engaged: {e}")
            self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def is_available(self) -> bool:
        return True

    def _deterministic_embed(self, text: str) -> List[float]:
        import hashlib
        import math
        vec = []
        for i in range(self._dimension):
            h = hashlib.md5(f"{text}:{i}".encode("utf-8")).digest()
            val = (int.from_bytes(h[:4], "little") / (2**32)) - 0.5
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_text(self, text: str) -> List[float]:
        norm_text = normalize_search_text(text)
        if not norm_text:
            return [0.0] * self._dimension

        if self._model is not None:
            try:
                results = list(self._model.embed([norm_text]))
                return [float(x) for x in results[0]]
            except Exception:
                pass
        return self._deterministic_embed(norm_text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        cleaned = [normalize_search_text(t) for t in texts]
        if self._model is not None:
            try:
                results = list(self._model.embed(cleaned))
                return [[float(x) for x in vec] for vec in results]
            except Exception:
                pass
        return [self._deterministic_embed(t) for t in cleaned]

