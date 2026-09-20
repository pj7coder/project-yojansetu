import logging
from pathlib import Path
from typing import Optional
import pymupdf

from app.core.config import get_settings
from app.ocr.interface import OCRPageRenderException

logger = logging.getLogger("jansetu.ocr.renderer")


class PDFPageRenderer:
    """Renders selected PDF pages to high-resolution images for OCR processing."""

    def __init__(self, dpi: Optional[int] = None):
        settings = get_settings()
        self.dpi = dpi or settings.ocr_render_dpi

    def render_page_to_image(
        self,
        pdf_path: Path,
        page_number: int,
        output_image_path: Path,
    ) -> Path:
        """
        Render a single 1-based physical page from original PDF to PNG.

        Args:
            pdf_path: Absolute or resolved path to original government PDF
            page_number: Physical 1-based page number
            output_image_path: Destination path for PNG file

        Returns:
            Path to rendered PNG file
        """
        if not pdf_path.exists():
            raise OCRPageRenderException(f"Original PDF file not found at {pdf_path}")

        output_image_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            doc = pymupdf.open(str(pdf_path))
            total_pages = doc.page_count

            if page_number < 1 or page_number > total_pages:
                raise OCRPageRenderException(
                    f"Invalid page number {page_number}. PDF contains {total_pages} pages."
                )

            # PyMuPDF uses 0-based page indices
            page = doc.load_page(page_number - 1)

            # Calculate zoom factor: standard PDF unit is 72 pt/inch
            zoom = self.dpi / 72.0
            matrix = pymupdf.Matrix(zoom, zoom)

            # Render page to pixmap (RGB, no alpha channel)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(str(output_image_path))
            doc.close()

            logger.info(
                "Rendered PDF page %d at %d DPI -> %s (width=%d, height=%d)",
                page_number,
                self.dpi,
                output_image_path.name,
                pix.width,
                pix.height,
            )
            return output_image_path

        except OCRPageRenderException:
            raise
        except Exception as exc:
            logger.error("Failed to render page %d of %s: %s", page_number, pdf_path, exc)
            raise OCRPageRenderException(
                f"Failed rendering page {page_number} from {pdf_path.name}: {exc}"
            ) from exc
