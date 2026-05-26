import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PdfBlockDTO:
    __slots__ = ("block_type", "text", "bbox", "page_number", "block_index")

    def __init__(
        self,
        *,
        block_type: str,
        text: str,
        bbox: list[float],
        page_number: int,
        block_index: int,
    ) -> None:
        self.block_type = block_type
        self.text = text
        self.bbox = bbox
        self.page_number = page_number
        self.block_index = block_index


class PdfClient:
    def __init__(self, *, render_dpi: int = 150) -> None:
        self._render_dpi = render_dpi

    def get_page_count(self, pdf_path: Path) -> int:
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        logger.info("get_page_count: path=%s pages=%d", pdf_path, count)
        return count

    def render_page(
        self,
        pdf_path: Path,
        page_index: int,
        output_path: Path,
        *,
        dpi: int | None = None,
    ) -> Path:
        """Render a single PDF page to a PNG image."""
        scale = (dpi or self._render_dpi) / 72.0
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix)
        pix.save(str(output_path))
        pix = None
        doc.close()
        logger.info(
            "render_page: path=%s page=%d output=%s dpi=%d",
            pdf_path,
            page_index + 1,
            output_path,
            dpi or self._render_dpi,
        )
        return output_path

    def extract_native_blocks(self, pdf_path: Path) -> list[PdfBlockDTO]:
        """Extract text blocks from all pages using PyMuPDF native extraction."""
        doc = fitz.open(str(pdf_path))
        blocks: list[PdfBlockDTO] = []

        for page_num, page in enumerate(doc):
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block_idx, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                text_parts: list[str] = []
                for line in lines:
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))
                text = "\n".join(text_parts).strip()
                if not text:
                    continue

                bbox = block.get("bbox", [0.0, 0.0, 0.0, 0.0])
                blocks.append(
                    PdfBlockDTO(
                        block_type="text",
                        text=text,
                        bbox=list(bbox),
                        page_number=page_num + 1,
                        block_index=block_idx,
                    )
                )

        doc.close()
        logger.info(
            "extract_native_blocks: path=%s total_blocks=%d",
            pdf_path,
            len(blocks),
        )
        return blocks

    def extract_page_text(self, pdf_path: Path, page_index: int) -> str:
        """Extract full text from a single page."""
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]
        text = page.get_text("text").strip()
        doc.close()
        return text

    def extract_page_as_pdf(self, pdf_path: Path, page_index: int) -> bytes:
        """Extract a single page from the PDF as a new single-page PDF (bytes)."""
        doc = fitz.open(str(pdf_path))
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
        page_pdf = new_doc.tobytes()
        new_doc.close()
        doc.close()
        logger.debug(
            "extract_page_as_pdf: path=%s page=%d size=%d bytes",
            pdf_path,
            page_index + 1,
            len(page_pdf),
        )
        return page_pdf
