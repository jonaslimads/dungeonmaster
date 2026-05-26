import logging
from pathlib import Path

from rag.clients.storage_client import StorageClient
from rag.clients.vlm_client import VlmClient
from rag.config import settings

logger = logging.getLogger(__name__)


class LayoutService:
    def __init__(self) -> None:
        self._vlm = VlmClient()
        self._storage = StorageClient()

    async def analyze_pages(
        self,
        *,
        source_id: str,
        page_range: range,
    ) -> list[dict]:
        """Run VLM layout analysis on a range of pages.

        Returns a list of skipped-page records with page_number and reason.
        Failed pages are skipped — the pipeline continues processing the rest.
        """
        pages_dir = self._storage.get_pages_dir(source_id)
        batch_size = settings.vlm_batch_pages
        layout_records: list[dict] = []
        skipped_pages: list[dict] = []

        for page_num in page_range:
            image_path = pages_dir / f"page_{page_num:04d}.png"
            if not image_path.exists():
                logger.warning(
                    "analyze_pages: image missing for page %d, skipping",
                    page_num,
                )
                skipped_pages.append({
                    "page_number": page_num,
                    "reason": "image_missing",
                })
                continue

            try:
                analysis = await self._vlm.analyze_page_layout(
                    page_image_path=image_path,
                    page_number=page_num,
                )
            except Exception as exc:
                logger.warning(
                    "analyze_pages: page=%d failed (%s), skipping",
                    page_num,
                    exc,
                )
                skipped_pages.append({
                    "page_number": page_num,
                    "reason": str(exc),
                })
                continue

            record = {
                "page_number": page_num,
                "markdown": analysis.markdown,
                "layout_blocks": [
                    {
                        "block_type": blk.block_type,
                        "text": blk.text,
                        "bbox": blk.bbox,
                        "reading_order": blk.reading_order,
                        "confidence": blk.confidence,
                    }
                    for blk in analysis.layout_blocks
                ],
                "visual_assets": [
                    {
                        "asset_type": asset.asset_type,
                        "title": asset.title,
                        "description": asset.description,
                        "bbox": asset.bbox,
                        "linked_text": asset.linked_text,
                        "useful_for_gameplay": asset.useful_for_gameplay,
                        "confidence": asset.confidence,
                    }
                    for asset in analysis.visual_assets
                ],
            }
            layout_records.append(record)

            if len(layout_records) >= batch_size:
                output = self._storage.get_extracted_dir(source_id) / "vlm_layout.jsonl"
                self._storage.save_jsonl(output, layout_records)
                logger.info(
                    "analyze_pages: source=%s flushed %d records",
                    source_id,
                    len(layout_records),
                )
                layout_records.clear()

        if layout_records:
            output = self._storage.get_extracted_dir(source_id) / "vlm_layout.jsonl"
            self._storage.save_jsonl(output, layout_records)

        if skipped_pages:
            logger.warning(
                "analyze_pages: source=%s skipped %d pages: %s",
                source_id,
                len(skipped_pages),
                ", ".join(f"p{r['page_number']}({r['reason'][:40]})" for r in skipped_pages),
            )

        logger.info(
            "analyze_pages: source=%s pages=%d-%d analyzed=%d skipped=%d",
            source_id,
            page_range[0],
            page_range[-1],
            len(layout_records) + sum(1 for _ in []),
            len(skipped_pages),
        )
        return skipped_pages

    async def close(self) -> None:
        await self._vlm.close()
