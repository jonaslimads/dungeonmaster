import logging
from pathlib import Path

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
    ) -> dict[str, str]:
        """Run the full extraction pipeline for a source in batches.

        Args:
            source_id: The registered source ID.
            pdf_path: Path to the original PDF.
            use_vlm: If True, run VLM layout analysis + asset detection.
            force: If True, start from scratch. If False, resume from
                   the last processed page.

        Each batch renders pages, extracts text, optionally runs VLM,
        and appends results to disk immediately.
        """
        logger.info(
            "run_pipeline: source=%s use_vlm=%s force=%s batch_size=%d",
            source_id,
            use_vlm,
            force,
            self._batch_size,
        )

        page_count = self._pdf.get_page_count(pdf_path)

        if force:
            self._clear_output(source_id)
            start_page = 1
        else:
            start_page = self._resume_page(source_id, page_count)
            logger.info(
                "run_pipeline: source=%s resuming from page %d",
                source_id,
                start_page,
            )

        all_native_blocks: list = []
        all_assets: list[dict] = []

        for batch_start in range(start_page, page_count + 1, self._batch_size):
            batch_end = min(batch_start + self._batch_size - 1, page_count)
            logger.info(
                "run_pipeline: source=%s batch %d-%d / %d",
                source_id,
                batch_start,
                batch_end,
                page_count,
            )

            # Render batch
            self._rendering.render_pages(
                source_id=source_id,
                pdf_path=pdf_path,
                page_range=range(batch_start, batch_end + 1),
            )

            # Extract native text for batch
            blocks = self._native_text.extract_and_save(
                source_id=source_id,
                pdf_path=pdf_path,
                page_range=range(batch_start, batch_end + 1),
            )
            all_native_blocks.extend(blocks)

            # VLM layout + asset detection (optional)
            if use_vlm:
                await self._layout.analyze_pages(
                    source_id=source_id,
                    page_range=range(batch_start, batch_end + 1),
                )
                layout_records = self._storage.load_jsonl(
                    self._storage.get_extracted_dir(source_id) / "vlm_layout.jsonl"
                )
                batch_assets = self._collect_visual_assets(layout_records)
                all_assets.extend(batch_assets)

                cropped = self._process_assets(
                    source_id=source_id,
                    assets=batch_assets,
                )
                all_assets = [
                    a for a in all_assets if a not in batch_assets
                ] + [c.model_dump() for c in cropped]

            # Build canonical markdown for batch (append)
            self._markdown.build_from_native_text(
                source_id=source_id,
                native_blocks=blocks,
                append=True,
            )

            logger.info(
                "run_pipeline: source=%s progress %d/%d pages",
                source_id,
                batch_end,
                page_count,
            )

        # Load previously extracted blocks if resuming
        if not force:
            prev_blocks = self._storage.load_jsonl(
                self._storage.get_extracted_dir(source_id) / "native_text.jsonl"
            )
            all_native_blocks = prev_blocks + all_native_blocks

        # Final quality report
        cropped_assets = all_assets if use_vlm else []
        report = self._generate_quality_report(
            source_id=source_id,
            page_count=page_count,
            native_blocks=all_native_blocks,
            assets=cropped_assets,
        )
        self._storage.save_text(
            self._storage.get_reports_dir(source_id) / "quality_report.md",
            report,
        )

        # Rebuild book.md from pages.jsonl
        self._markdown.rebuild_book_md(source_id)

        return {
            "source_id": source_id,
            "page_count": str(page_count),
            "native_blocks": str(len(all_native_blocks)),
            "visual_assets": str(len(cropped_assets)),
            "status": "completed",
        }

    def _resume_page(self, source_id: str, total_pages: int) -> int:
        """Detect the next page to process based on existing output files."""
        pages_dir = self._storage.get_pages_dir(source_id)
        if not pages_dir.exists():
            return 1

        rendered = set()
        for f in pages_dir.glob("page_*.png"):
            try:
                num = int(f.stem.split("_")[1])
                rendered.add(num)
            except (ValueError, IndexError):
                continue

        if not rendered:
            return 1

        max_rendered = max(rendered)

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
                # Use the lower of rendered vs text-extracted
                # (if pages were rendered but text wasn't extracted, re-process)
                if max_text < max_rendered:
                    max_rendered = max_text
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
                if max_canonical < max_rendered:
                    max_rendered = max_canonical
            else:
                return 1
        else:
            return 1

        next_page = max_rendered + 1
        if next_page > total_pages:
            logger.info(
                "_resume_page: source=%s already complete (%d/%d)",
                source_id,
                max_rendered,
                total_pages,
            )
            return total_pages + 1

        return next_page

    def _clear_output(self, source_id: str) -> None:
        """Clear previous output files for a fresh run."""
        pages_dir = self._storage.get_pages_dir(source_id)
        if pages_dir.exists():
            for f in pages_dir.glob("*.png"):
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
        """Process visual assets: validate, crop, save."""
        from PIL import Image

        pages_dir = self._storage.get_pages_dir(source_id)
        sample_image = pages_dir / "page_0001.png"

        page_width, page_height = 800, 1100
        if sample_image.exists():
            with Image.open(str(sample_image)) as img:
                page_width, page_height = img.size

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
        self._visual_asset.save_assets(source_id=source_id, assets=cropped)
        return cropped

    async def close(self) -> None:
        await self._layout.close()

    def _collect_visual_assets(self, layout_records: list[dict]) -> list[dict]:
        """Collect all visual asset detections from VLM layout records."""
        assets: list[dict] = []
        for record in layout_records:
            for va in record.get("visual_assets", []):
                assets.append({
                    "page_number": record.get("page_number", 1),
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
