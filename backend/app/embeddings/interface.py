from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """
    Abstract contract for text embedding generation.
    Decouples model execution from business discovery logic.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name or HuggingFace repo of the embedding model."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """True if the embedding model is loaded and ready for offline inference."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate normalized dense embedding for a single text snippet."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized dense embeddings for a batch of text snippets."""
        pass
