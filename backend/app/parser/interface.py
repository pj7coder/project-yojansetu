from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class BlockType:
    TITLE = "TITLE"
    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    LIST_ITEM = "LIST_ITEM"
    TABLE = "TABLE"
    CAPTION = "CAPTION"
    FOOTNOTE = "FOOTNOTE"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    UNKNOWN = "UNKNOWN"


class PageTextStatus:
    TEXT_OK = "TEXT_OK"          # Normal extractable digital text (>= 100 characters)
    LOW_TEXT = "LOW_TEXT"        # Sparse text (1 to 99 characters)
    NO_TEXT = "NO_TEXT"          # Zero characters (scanned / image-only page)
    PARSE_ERROR = "PARSE_ERROR"  # Garbled or corrupt page output


class ParserException(Exception):
    """Base exception for parsing failures."""
    pass


class MinerUUnavailableException(ParserException):
    """Raised when MinerU CLI binary or Python package is not found or cannot execute."""
    pass


class ParserTimeoutException(ParserException):
    """Raised when parsing exceeds configured timeout threshold."""
    pass


class ParserExecutionException(ParserException):
    """Raised when parser crashes or returns non-zero exit code."""
    pass


class DocumentPageLimitExceededException(ParserException):
    """Raised when document page count exceeds MAX_PARSE_PAGES."""
    def __init__(self, page_count: int, max_pages: int):
        super().__init__(f"Document page count ({page_count}) exceeds limit ({max_pages})")
        self.page_count = page_count
        self.max_pages = max_pages


@dataclass
class RawTableData:
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    markdown: Optional[str] = None


@dataclass
class RawBlockData:
    page_number: int  # 1-based canonical physical page number
    order_index: int  # Reading order sequence (0, 1, 2...)
    block_type: str   # BlockType constant
    text: str
    section_path: List[str] = field(default_factory=list)
    table_data: Optional[RawTableData] = None
    bbox: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPageData:
    page_number: int  # 1-based canonical physical page number
    blocks: List[RawBlockData] = field(default_factory=list)
    raw_text: str = ""
    image_count: int = 0


@dataclass
class ParserRawResult:
    """Raw structured result emitted by any parser adapter prior to normalization."""
    success: bool
    parser_name: str
    parser_version: str
    page_count: int
    pages: List[RawPageData] = field(default_factory=list)
    raw_output_dir: Optional[Path] = None
    raw_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: int = 0


class BaseParser(ABC):
    """Abstract interface for all YojanSetu document layout parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the parser implementation."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the parser implementation."""
        pass

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        raw_output_dir: Path,
        max_pages: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        device: str = "auto",
        **kwargs: Any,
    ) -> ParserRawResult:
        """
        Execute parsing on target PDF and emit raw structured pages and blocks.
        """
        pass
