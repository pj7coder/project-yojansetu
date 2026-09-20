import abc
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class OCRStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SKIPPED_NOT_NEEDED = "SKIPPED_NOT_NEEDED"


class PageOCRReason(str, Enum):
    NO_TEXT_WITH_IMAGE = "NO_TEXT_WITH_IMAGE"
    LIKELY_SCANNED = "LIKELY_SCANNED"
    GARBLED_TEXT = "GARBLED_TEXT"
    PARSE_ERROR = "PARSE_ERROR"
    BLANK_DIVIDER = "BLANK_DIVIDER"
    TEXT_OK = "TEXT_OK"
    MANUAL_REQUEST = "MANUAL_REQUEST"


class ExtractionMethod(str, Enum):
    MINERU = "MINERU"
    PADDLEOCR = "PADDLEOCR"
    MERGED = "MERGED"


class OCRError(Exception):
    """Base exception for OCR subsystem."""
    pass


class OCREngineUnavailableException(OCRError):
    """Raised when the specified OCR engine cannot be initialized or binaries are absent."""
    pass


class OCRPageRenderException(OCRError):
    """Raised when page rendering from PDF fails."""
    pass


class OCRMergeException(OCRError):
    """Raised when merging OCR outputs with MinerU outputs fails validation."""
    pass


@dataclass
class OCRRegion:
    """A detected and recognized text region on a page with spatial coordinates."""
    text: str
    bbox: List[float]  # [x0, y0, x1, y1]
    ocr_confidence: float
    is_numeric: bool = False
    low_confidence_numeric: bool = False
    order_index: int = 0
    block_type: str = "PARAGRAPH"


@dataclass
class OCRPageResult:
    """Normalized OCR output for a single physical PDF page."""
    page_number: int
    success: bool
    engine: str
    regions: List[OCRRegion] = field(default_factory=list)
    raw_text: str = ""
    duration_ms: int = 0
    error_message: Optional[str] = None
    raw_output: Optional[Any] = None


@dataclass
class PageOCRDecision:
    """Deterministic assessment of whether a page requires OCR fallback."""
    page_number: int
    needs_ocr: bool
    reason: str
    text_character_count: int
    image_count: int
    garbled_ratio: float


@dataclass
class OCRDecisionResult:
    """Document-level OCR requirement decision."""
    document_id: str
    ocr_required: bool
    pages_total: int
    pages_needing_ocr: List[int]
    page_decisions: List[PageOCRDecision] = field(default_factory=list)


class OCRProvider(abc.ABC):
    """Abstract interface for local OCR recognition providers."""

    @property
    @abc.abstractmethod
    def engine_name(self) -> str:
        """Name of the OCR provider engine."""
        pass

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Version string of the provider engine."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Verify whether provider dependencies and local models are present."""
        pass

    @abc.abstractmethod
    def ocr_page(self, image_path: Path, page_number: int, **kwargs) -> OCRPageResult:
        """Perform OCR on a rendered page image."""
        pass
