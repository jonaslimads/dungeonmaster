import logging
from pathlib import Path

from rag.clients.pdf_client import PdfClient, PdfBlockDTO
from rag.clients.storage_client import StorageClient

logger = logging.getLogger(__name__)


def _merge_drop_caps(lines: list[str]) -> list[str]:
    """Merge single-character drop-cap lines into the following line.

    PDFs with decorative initial letters (drop caps) extract the large letter
    as a separate text element. This function detects a line that is exactly
    one alphabetic character and merges it with the next line.

    Example: ["C", "APÍTULO", " ", "3", ":", "C", "LASSES"]
             -> ["CAPÍTULO", " ", "3", ":", "CLASSES"]
    """
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if len(line) == 1 and line.isalpha() and i + 1 < len(lines):
            result.append(line + lines[i + 1])
            i += 2
        else:
            result.append(lines[i])
            i += 1
    return result


class NativeTextService:
    def __init__(self) -> None:
        self._pdf = PdfClient()
        self._storage = StorageClient()

    def extract(
        self,
        *,
        source_id: str,
        pdf_path: Path,
        page_range: range,
    ) -> list[PdfBlockDTO]:
        """Extract native text blocks for a page range (in-memory only)."""
        doc = __import__("fitz", fromlist=["open"]).open(str(pdf_path))
        blocks: list[PdfBlockDTO] = []

        for page_num in page_range:
            page = doc[page_num - 1]
            text_dict = page.get_text("dict", flags=__import__("fitz", fromlist=["TEXT_PRESERVE_WHITESPACE"]).TEXT_PRESERVE_WHITESPACE)
            for block_idx, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                text_parts: list[str] = []
                for line in lines:
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))

                merged_parts = _merge_drop_caps(text_parts)
                text = "\n".join(merged_parts).strip()
                if not text:
                    continue

                bbox = block.get("bbox", [0.0, 0.0, 0.0, 0.0])
                blocks.append(
                    PdfBlockDTO(
                        block_type="text",
                        text=text,
                        bbox=list(bbox),
                        page_number=page_num,
                        block_index=block_idx,
                    )
                )

        doc.close()

        logger.info(
            "extract: source=%s pages=%d-%d blocks=%d",
            source_id,
            page_range[0],
            page_range[-1],
            len(blocks),
        )
        return blocks
