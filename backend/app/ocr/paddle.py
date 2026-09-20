import importlib.util
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.ocr.interface import (
    OCREngineUnavailableException,
    OCRError,
    OCRPageResult,
    OCRProvider,
    OCRRegion,
)

logger = logging.getLogger("jansetu.ocr.paddle")

# Regex to detect Rajasthan scheme numbers, currency, dates, percentages, and limits
# Supports ASCII digits 0-9 and Devanagari numerals ०-९
NUMERIC_REGEX = re.compile(
    r"(?:₹\s*[\d,०-९]+|"
    r"[\d,०-९]+(?:\.\d+)?\s*(?:%|प्रतिशत|वर्ष|साल|years?|हेक्टेयर|hectares?|लाख|हज़ार|करोड़)|"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|"
    r"(?:\b[\d०-९]{2,}\b))",
    re.IGNORECASE,
)


def is_numeric_text(text: str) -> bool:
    """Detect if text contains critical scheme numeric indicators."""
    return bool(NUMERIC_REGEX.search(text))


def sort_regions_reading_order(regions: List[OCRRegion], line_tolerance: float = 15.0) -> List[OCRRegion]:
    """
    Sort bounding boxes into natural reading order (top-to-bottom, left-to-right).
    Groups boxes with similar y-coordinates into horizontal lines.
    """
    if not regions:
        return []

    # Sort primarily by y0
    sorted_by_y = sorted(regions, key=lambda r: r.bbox[1])
    lines: List[List[OCRRegion]] = []

    for reg in sorted_by_y:
        y0 = reg.bbox[1]
        placed = False
        for line in lines:
            # Check if region aligns vertically with the line's average y0
            avg_y0 = sum(r.bbox[1] for r in line) / len(line)
            if abs(y0 - avg_y0) <= line_tolerance:
                line.append(reg)
                placed = True
                break
        if not placed:
            lines.append([reg])

    # Sort each line left-to-right by x0
    result: List[OCRRegion] = []
    order_idx = 0
    for line in lines:
        line_sorted = sorted(line, key=lambda r: r.bbox[0])
        for r in line_sorted:
            r.order_index = order_idx
            order_idx += 1
            result.append(r)

    return result


class PaddleOCRAdapter(OCRProvider):
    """Local PaddleOCR adapter supporting Hindi, English, and bilingual documents."""

    def __init__(
        self,
        lang: str = "hi",
        device: Optional[str] = None,
    ):
        settings = get_settings()
        self.lang = lang
        self.device = device or settings.ocr_device
        self._engine: Any = None
        self._available: Optional[bool] = None

    @property
    def engine_name(self) -> str:
        return "paddleocr"

    @property
    def version(self) -> str:
        return "2.7.0"

    def is_available(self) -> bool:
        """Check if paddle and paddleocr modules are importable."""
        if self._available is not None:
            return self._available

        has_paddle = importlib.util.find_spec("paddle") is not None
        has_paddleocr = importlib.util.find_spec("paddleocr") is not None
        self._available = has_paddle and has_paddleocr
        return self._available

    def _get_engine(self) -> Any:
        """Lazily initialize PaddleOCR instance."""
        if not self.is_available():
            raise OCREngineUnavailableException(
                "PaddleOCR is not installed or configured in this environment. "
                "Ensure paddlepaddle and paddleocr packages are installed."
            )

        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
                use_gpu = self.device.lower() in ("gpu", "cuda")
                self._engine = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.lang,
                    use_gpu=use_gpu,
                    show_log=False,
                )
                logger.info(
                    "Initialized PaddleOCR engine (lang=%s, device=%s)",
                    self.lang,
                    self.device,
                )
            except Exception as exc:
                logger.error("Failed to initialize PaddleOCR: %s", exc)
                raise OCREngineUnavailableException(
                    f"PaddleOCR initialization failed: {exc}"
                ) from exc

        return self._engine

    def ocr_page(self, image_path: Path, page_number: int, **kwargs) -> OCRPageResult:
        """Perform OCR on a rendered page image using local PaddleOCR."""
        if not image_path.exists():
            return OCRPageResult(
                page_number=page_number,
                success=False,
                engine=self.engine_name,
                error_message=f"Image file not found: {image_path}",
            )

        start_time = time.perf_counter()
        engine = self._get_engine()
        settings = get_settings()

        try:
            raw_output = engine.ocr(str(image_path), cls=True)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            regions: List[OCRRegion] = []
            if raw_output and raw_output[0]:
                for item in raw_output[0]:
                    box_points, (text, conf) = item
                    # box_points is [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                    xs = [pt[0] for pt in box_points]
                    ys = [pt[1] for pt in box_points]
                    bbox = [min(xs), min(ys), max(xs), max(ys)]

                    is_num = is_numeric_text(text)
                    low_conf_num = is_num and (conf < settings.ocr_numeric_confidence_threshold)

                    regions.append(
                        OCRRegion(
                            text=text.strip(),
                            bbox=bbox,
                            ocr_confidence=float(conf),
                            is_numeric=is_num,
                            low_confidence_numeric=low_conf_num,
                        )
                    )

            # Sort regions into natural reading order
            sorted_regions = sort_regions_reading_order(regions)
            raw_text = "\n".join(r.text for r in sorted_regions)

            return OCRPageResult(
                page_number=page_number,
                success=True,
                engine=self.engine_name,
                regions=sorted_regions,
                raw_text=raw_text,
                duration_ms=duration_ms,
                raw_output=raw_output,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("PaddleOCR execution failed on page %d: %s", page_number, exc)
            return OCRPageResult(
                page_number=page_number,
                success=False,
                engine=self.engine_name,
                duration_ms=duration_ms,
                error_message=str(exc),
            )


class MockOCRProvider(OCRProvider):
    """
    Deterministic offline OCR provider for test suites and environments
    without heavy deep learning packages installed.
    """

    def __init__(self, simulated_texts: Optional[Dict[int, str]] = None, fail_pages: Optional[List[int]] = None):
        self.simulated_texts = simulated_texts or {}
        self.fail_pages = fail_pages or []

    @property
    def engine_name(self) -> str:
        return "mock"

    @property
    def version(self) -> str:
        return "1.0.0-mock"

    def is_available(self) -> bool:
        return True

    def ocr_page(self, image_path: Path, page_number: int, **kwargs) -> OCRPageResult:
        """Simulate OCR recognition deterministically."""
        start_time = time.perf_counter()

        if page_number in self.fail_pages:
            return OCRPageResult(
                page_number=page_number,
                success=False,
                engine=self.engine_name,
                duration_ms=5,
                error_message=f"Simulated OCR failure on page {page_number}",
            )

        settings = get_settings()

        # Check if custom text configured for this page
        if page_number in self.simulated_texts:
            text_lines = self.simulated_texts[page_number].strip().split("\n")
        else:
            # Default simulated Rajasthan government notification text
            text_lines = [
                "राजस्थान सरकार - सामाजिक न्याय एवं अधिकारिता विभाग",
                "मुख्यमंत्री अनुप्रति कोचिंग योजना 2026",
                "पात्रता: आवेदक राजस्थान का मूल निवासी होना चाहिए।",
                "वार्षिक आय सीमा: परिवार की वार्षिक आय ₹2,00,000 से कम होनी चाहिए।",
                "आयु सीमा: 18 वर्ष से 60 वर्ष।",
                "आवेदन की अंतिम तिथि: 31/03/2026",
                "आवश्यक दस्तावेज: आधार कार्ड, जन आधार कार्ड, आय प्रमाण पत्र।",
            ]

        regions: List[OCRRegion] = []
        y_offset = 50.0

        for idx, line in enumerate(text_lines):
            line = line.strip()
            if not line:
                continue

            bbox = [50.0, y_offset, 550.0, y_offset + 30.0]
            y_offset += 40.0

            # Set confidence: by default 0.95, or lower if specified in kwargs
            conf = kwargs.get("simulated_confidence", 0.95)
            is_num = is_numeric_text(line)
            low_conf_num = is_num and (conf < settings.ocr_numeric_confidence_threshold)

            # Assign block type based on heuristics
            b_type = "HEADING" if idx == 0 else "PARAGRAPH"
            if "तालिका" in line or "Table" in line or "|" in line:
                b_type = "TABLE_TEXT"

            regions.append(
                OCRRegion(
                    text=line,
                    bbox=bbox,
                    ocr_confidence=conf,
                    is_numeric=is_num,
                    low_confidence_numeric=low_conf_num,
                    order_index=idx,
                    block_type=b_type,
                )
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        raw_text = "\n".join(r.text for r in regions)

        return OCRPageResult(
            page_number=page_number,
            success=True,
            engine=self.engine_name,
            regions=regions,
            raw_text=raw_text,
            duration_ms=max(duration_ms, 5),
            raw_output={"mock_regions_count": len(regions)},
        )
