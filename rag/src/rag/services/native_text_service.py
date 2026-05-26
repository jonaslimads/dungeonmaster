import logging
from pathlib import Path

from rag.clients.pdf_client import PdfClient, PdfBlockDTO
from rag.clients.storage_client import StorageClient

logger = logging.getLogger(__name__)


class NativeTextService:
    def __init__(self) -> None:
        self._pdf = PdfClient()
        self._storage = StorageClient()

    def extract_and_save(
        self,
        *,
        source_id: str,
        pdf_path: Path,
        page_range: range,
    ) -> list[PdfBlockDTO]:
        """Extract native text blocks for a page range and append to native_text.jsonl."""
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
                text = "\n".join(text_parts).strip()
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

        records = [
            {
                "page_number": blk.page_number,
                "block_index": blk.block_index,
                "block_type": blk.block_type,
                "text": blk.text,
                "bbox": blk.bbox,
            }
            for blk in blocks
        ]

        output = self._storage.get_extracted_dir(source_id) / "native_text.jsonl"
        self._storage.save_jsonl(output, records)

        logger.info(
            "extract_and_save: source=%s pages=%d-%d blocks=%d",
            source_id,
            page_range[0],
            page_range[-1],
            len(blocks),
        )
        return blocks
