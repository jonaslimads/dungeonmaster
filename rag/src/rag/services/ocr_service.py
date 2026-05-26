import logging
from pathlib import Path

from rag.clients.ocr_client import OcrClient
from rag.clients.storage_client import StorageClient

logger = logging.getLogger(__name__)


class OcrService:
    def __init__(self) -> None:
        self._ocr = OcrClient()
        self._storage = StorageClient()

    async def run_ocr_on_pages(
        self,
        *,
        source_id: str,
        page_numbers: list[int],
    ) -> None:
        """Run VLM OCR on specific pages and save results."""
        pages_dir = self._storage.get_pages_dir(source_id)
        all_blocks: list[dict] = []

        for page_num in page_numbers:
            image_path = pages_dir / f"page_{page_num:04d}.png"
            if not image_path.exists():
                logger.warning(
                    "run_ocr: page image missing: %s",
                    image_path,
                )
                continue

            blocks = await self._ocr.extract_text_from_image(
                image_path=image_path,
                page_number=page_num,
            )
            all_blocks.extend(
                {
                    "page_number": blk.page_number,
                    "text": blk.text,
                    "bbox": blk.bbox,
                    "confidence": blk.confidence,
                }
                for blk in blocks
            )

        output = self._storage.get_extracted_dir(source_id) / "ocr_blocks.jsonl"
        self._storage.save_jsonl(output, all_blocks)

        logger.info(
            "run_ocr_on_pages: source=%s pages=%d total_blocks=%d",
            source_id,
            len(page_numbers),
            len(all_blocks),
        )

    async def close(self) -> None:
        await self._ocr.close()
