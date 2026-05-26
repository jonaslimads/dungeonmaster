import logging
from pathlib import Path

import fitz

from rag.clients.pdf_client import PdfClient
from rag.clients.storage_client import StorageClient
from rag.services.image_cropping_service import ImageCroppingService
from rag.services.layout_service import LayoutService
from rag.services.markdown_service import MarkdownService
from rag.services.native_text_service import NativeTextService
from rag.services.page_rendering_service import PageRenderingService
from rag.services.source_service import SourceService
from rag.services.visual_asset_service import VisualAssetService

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the full PDF extraction pipeline.

    Delegates to specialized services; does not perform extraction itself.
    Processes pages in batches and saves incrementally to disk.
    """

    def __init__(self, *, batch_size: int = 10) -> None:
        self._source = SourceService()
        self._pdf = PdfClient()
        self._rendering = PageRenderingService()
        self._native_text = NativeTextService()
        self._layout = LayoutService()
        self._visual_asset = VisualAssetService()
        self._cropping = ImageCroppingService()
        self._markdown = MarkdownService()
        self._storage = StorageClient()
        self._batch_size = batch_size

    async def run_pipeline(
        self,
        *,
        source_id: str,
        pdf_path: Path,
        use_vlm: bool = False,
        force: bool = False,
        offset: int = 0,
        limit: int = 0,
        batch_size: int | None = None,
    ) -> dict[str, str]:
        """Run the full extraction pipeline for a source in batches.

        Args:
            source_id: The registered source ID.
            pdf_path: Path to the original PDF.
            use_vlm: If True, run VLM layout analysis + asset detection.
            force: If True, start from scratch. If False, resume from
                   the last processed page.
            offset: 0-based page offset (first page = offset 0).
            limit: Max pages to process (0 = all remaining pages).
            batch_size: Pages per batch (default from constructor).

        Each batch renders pages, extracts text, optionally runs VLM,
        and appends results to disk immediately.
        """
        bs = batch_size if batch_size is not None else self._batch_size
        logger.info(
            "run_pipeline: source=%s use_vlm=%s force=%s offset=%d limit=%d batch_size=%d",
            source_id,
            use_vlm,
            force,
            offset,
            limit,
            bs,
        )

        page_count = self._pdf.get_page_count(pdf_path)

        # Compute the effective page range from offset + limit
        first_page = offset + 1  # 1-based
        last_page = page_count if limit == 0 else first_page + limit - 1
        last_page = min(last_page, page_count)  # cap at total

        if force:
            self._clear_output(source_id)
            start_page = first_page
        else:
            start_page = self._resume_page(source_id, page_count)
            start_page = max(start_page, first_page)  # don't go before offset
            logger.info(
                "run_pipeline: source=%s resuming from page %d",
                source_id,
                start_page,
            )

        all_native_blocks: list = []
        all_assets: list[dict] = []
        all_vlm_skipped: list[dict] = []
        seen_asset_ids: set[str] = set()

        for batch_start in range(start_page, last_page + 1, bs):
            batch_end = min(batch_start + bs - 1, last_page)
            logger.info(
                "run_pipeline: source=%s batch %d-%d / %d",
                source_id,
                batch_start,
                batch_end,
                page_count,
            )

            # Extract batch as single-page PDFs
            self._rendering.extract_pages(
                source_id=source_id,
                pdf_path=pdf_path,
                page_range=range(batch_start, batch_end + 1),
            )

            # Extract native text for batch
            blocks = self._native_text.extract(
                source_id=source_id,
                pdf_path=pdf_path,
                page_range=range(batch_start, batch_end + 1),
            )
            all_native_blocks.extend(blocks)

            # VLM layout + asset detection (optional)
            if use_vlm:
                skipped = await self._layout.analyze_pages(
                    source_id=source_id,
                    pdf_path=pdf_path,
                    page_range=range(batch_start, batch_end + 1),
                )
                all_vlm_skipped.extend(skipped)

                layout_records = self._storage.load_jsonl(
                    self._storage.get_extracted_dir(source_id) / "vlm_layout.jsonl"
                )
                batch_assets = self._collect_visual_assets(
                    layout_records,
                    page_range=range(batch_start, batch_end + 1),
                )
                new_assets = [
                    a for a in batch_assets
                    if a.get("id", str(a)) not in seen_asset_ids
                ]
                seen_asset_ids.update(a.get("id", str(a)) for a in new_assets)
                all_assets.extend(new_assets)

            # --- Flush batch results to disk ---

            # Save native text blocks (append)
            native_records = [
                {
                    "page_number": blk.page_number,
                    "block_index": blk.block_index,
                    "block_type": blk.block_type,
                    "text": blk.text,
                    "bbox": blk.bbox,
                }
                for blk in blocks
            ]
            self._storage.save_jsonl(
                self._storage.get_extracted_dir(source_id) / "native_text.jsonl",
                native_records,
            )

            # Build canonical pages.jsonl + book.md from this batch
            self._markdown.build_from_native_text(
                source_id=source_id,
                native_blocks=blocks,
                append=True,
            )
            self._markdown.rebuild_book_md(source_id)

            # Append skipped VLM pages (if any)
            if use_vlm and skipped:
                self._storage.save_jsonl(
                    self._storage.get_extracted_dir(source_id) / "vlm_skipped.jsonl",
                    skipped,
                )

            logger.info(
                "run_pipeline: source=%s batch %d-%d flushed to disk",
                source_id,
                batch_start,
                batch_end,
            )
            logger.info(
                "run_pipeline: source=%s progress %d/%d pages",
                source_id,
                batch_end,
                page_count,
            )

        # --- Final aggregation (after all batches) ---

        logger.info(
            "run_pipeline: source=%s all batches done, %d native blocks total",
            source_id,
            len(all_native_blocks),
        )

        # Process all visual assets at once (crop + save)
        cropped_assets: list[dict] = []
        if use_vlm and all_assets:
            cropped_models = self._process_assets(
                source_id=source_id,
                assets=all_assets,
            )
            cropped_assets = [m.model_dump() for m in cropped_models]
            self._visual_asset.save_assets(source_id=source_id, assets=cropped_models)
            logger.info(
                "run_pipeline: source=%s saved %d visual assets",
                source_id,
                len(cropped_assets),
            )

        # Save final quality report
        if use_vlm and all_vlm_skipped:
            skipped_path = (
                self._storage.get_extracted_dir(source_id) / "vlm_skipped.jsonl"
            )
            logger.info(
                "run_pipeline: source=%s total %d skipped VLM pages",
                source_id,
                len(all_vlm_skipped),
            )

        # Final quality report
        report = self._generate_quality_report(
            source_id=source_id,
            page_count=page_count,
            native_blocks=all_native_blocks,
            assets=cropped_assets,
            vlm_skipped=all_vlm_skipped if use_vlm else [],
        )
        self._storage.save_text(
            self._storage.get_reports_dir(source_id) / "quality_report.md",
            report,
        )

        return {
            "source_id": source_id,
            "page_count": str(page_count),
            "native_blocks": str(len(all_native_blocks)),
            "visual_assets": str(len(cropped_assets)),
            "vlm_skipped_pages": str(len(all_vlm_skipped)),
            "status": "completed",
        }

    def _resume_page(self, source_id: str, total_pages: int) -> int:
        """Detect the next page to process based on existing output files."""
        pages_dir = self._storage.get_pages_dir(source_id)
        if not pages_dir.exists():
            return 1

        extracted = set()
        for f in pages_dir.glob("page_*.pdf"):
            try:
                num = int(f.stem.split("_")[1])
                extracted.add(num)
            except (ValueError, IndexError):
                continue

        if not extracted:
            return 1

        max_extracted = max(extracted)

        # Check native_text.jsonl to confirm text was extracted
        native_path = (
            self._storage.get_extracted_dir(source_id) / "native_text.jsonl"
        )
        if native_path.exists():
            records = self._storage.load_jsonl(native_path)
            if records:
                pages_with_text = {
                    r.get("page_number") for r in records
                }
                max_text = max(pages_with_text) if pages_with_text else 0
                # Use the lower of extracted vs text-extracted
                # (if pages were extracted but text wasn't, re-process)
                if max_text < max_extracted:
                    max_extracted = max_text
            else:
                return 1
        else:
            return 1

        # Check canonical/pages.jsonl
        pages_jsonl = (
            self._storage.get_canonical_dir(source_id) / "pages.jsonl"
        )
        if pages_jsonl.exists():
            records = self._storage.load_jsonl(pages_jsonl)
            if records:
                pages_canonical = {
                    r.get("page_number") for r in records
                }
                max_canonical = max(pages_canonical) if pages_canonical else 0
                if max_canonical < max_extracted:
                    max_extracted = max_canonical
            else:
                return 1
        else:
            return 1

        next_page = max_extracted + 1
        if next_page > total_pages:
            logger.info(
                "_resume_page: source=%s already complete (%d/%d)",
                source_id,
                max_extracted,
                total_pages,
            )
            return total_pages + 1

        return next_page

    def _clear_output(self, source_id: str) -> None:
        """Clear previous output files for a fresh run."""
        pages_dir = self._storage.get_pages_dir(source_id)
        if pages_dir.exists():
            for f in pages_dir.glob("*.pdf"):
                f.unlink()

        assets_images = self._storage.get_assets_images_dir(source_id)
        if assets_images.exists():
            for f in assets_images.glob("*"):
                f.unlink()

        assets_thumbs = self._storage.get_assets_thumbnails_dir(source_id)
        if assets_thumbs.exists():
            for f in assets_thumbs.glob("*"):
                f.unlink()

        files_to_clear = [
            self._storage.get_extracted_dir(source_id) / "native_text.jsonl",
            self._storage.get_extracted_dir(source_id) / "vlm_layout.jsonl",
            self._storage.get_extracted_dir(source_id) / "ocr_blocks.jsonl",
            self._storage.get_extracted_dir(source_id) / "image_assets.jsonl",
            self._storage.get_extracted_dir(source_id) / "vlm_skipped.jsonl",
            self._storage.get_canonical_dir(source_id) / "pages.jsonl",
            self._storage.get_canonical_dir(source_id) / "book.md",
            self._storage.get_reports_dir(source_id) / "quality_report.md",
        ]
        for f in files_to_clear:
            if f.exists():
                f.unlink()

    def _process_assets(
        self,
        *,
        source_id: str,
        assets: list[dict],
    ) -> list:
        """Process visual assets: validate and crop."""
        import fitz

        from rag.clients.storage_client import StorageClient

        pdf_path = Path(
            StorageClient.get_original_dir(source_id) / "source.pdf"
        )
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        page_width = int(page.rect.width)
        page_height = int(page.rect.height)
        doc.close()

        page_assets_map: dict[int, list[dict]] = {}
        for asset_info in assets:
            pn = asset_info.get("page_number", 1)
            page_assets_map.setdefault(pn, []).append(asset_info)

        all_image_assets = []
        for pn, detections in sorted(page_assets_map.items()):
            created = self._visual_asset.create_assets_from_vlm(
                source_id=source_id,
                page_number=pn,
                page_width=page_width,
                page_height=page_height,
                vlm_assets=detections,
            )
            all_image_assets.extend(created)

        if not all_image_assets:
            return []

        cropped = self._cropping.crop_all(
            source_id=source_id,
            assets=all_image_assets,
        )
        return cropped

    async def close(self) -> None:
        await self._layout.close()

    def _collect_visual_assets(
        self,
        layout_records: list[dict],
        page_range: range | None = None,
    ) -> list[dict]:
        """Collect visual asset detections from VLM layout records.

        If page_range is given, only collect assets from those pages.
        """
        assets: list[dict] = []
        allowed_pages = set(page_range) if page_range else None

        for record in layout_records:
            pn = record.get("page_number", 1)
            if allowed_pages is not None and pn not in allowed_pages:
                continue
            for va in record.get("visual_assets", []):
                assets.append({
                    "page_number": pn,
                    **va,
                })
        return assets

    def _generate_quality_report(
        self,
        *,
        source_id: str,
        page_count: int,
        native_blocks: list,
        assets: list[dict],
        vlm_skipped: list[dict] | None = None,
    ) -> str:
        """Generate a quality report markdown document."""
        text_length_per_page: dict[int, int] = {}
        for blk in native_blocks:
            if isinstance(blk, dict):
                pn = blk.get("page_number", 0)
                text = blk.get("text", "")
            else:
                pn = blk.page_number
                text = blk.text or ""
            text_length_per_page[pn] = text_length_per_page.get(pn, 0) + len(text)

        low_text_pages = [
            pn for pn, length in text_length_per_page.items()
            if length < 50
        ]
        no_text_pages = [
            pn for pn in range(1, page_count + 1)
            if pn not in text_length_per_page
        ]

        asset_types: dict[str, int] = {}
        gameplay_useful = 0
        low_confidence = 0
        for asset in assets:
            atype = asset.get("asset_type", "unknown")
            asset_types[atype] = asset_types.get(atype, 0) + 1
            if asset.get("useful_for_gameplay"):
                gameplay_useful += 1
            if asset.get("confidence", 1.0) < 0.5:
                low_confidence += 1

        lines = [
            f"# Quality Report — {source_id}",
            "",
            "## Summary",
            f"- Total pages: {page_count}",
            f"- Pages with text: {len(text_length_per_page)}",
            f"- Pages with no text: {len(no_text_pages)}",
            f"- Pages with low text (< 50 chars): {len(low_text_pages)}",
            f"- Total native text blocks: {len(native_blocks)}",
            "",
            "## Visual Assets",
            f"- Total detected: {len(assets)}",
            f"- Gameplay useful: {gameplay_useful}",
        ]

        for atype, count in sorted(asset_types.items()):
            lines.append(f"- {atype}: {count}")

        lines.extend([
            f"- Low confidence (< 0.5): {low_confidence}",
            "",
        ])

        if vlm_skipped:
            lines.append("## VLM Skipped Pages")
            lines.append(f"- Pages skipped during VLM analysis: {len(vlm_skipped)}")
            for entry in sorted(vlm_skipped, key=lambda e: e.get("page_number", 0)):
                pn = entry.get("page_number", "?")
                reason = entry.get("reason", "unknown")
                lines.append(f"- Page {pn}: {reason}")
            lines.append("")

        if no_text_pages:
            lines.append("## Pages with no extracted text")
            for pn in no_text_pages:
                lines.append(f"- Page {pn}")
            lines.append("")

        if low_text_pages:
            lines.append("## Pages with low text content")
            for pn in low_text_pages:
                lines.append(f"- Page {pn}")
            lines.append("")

        return "\n".join(lines)
