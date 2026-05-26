import logging
from pathlib import Path

from rag.clients.pdf_client import PdfBlockDTO
from rag.clients.storage_client import StorageClient
from rag.models.block import PageBlock
from rag.models.page import ExtractedPage

logger = logging.getLogger(__name__)


class MarkdownService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def build_from_native_text(
        self,
        *,
        source_id: str,
        native_blocks: list[PdfBlockDTO],
        append: bool = True,
    ) -> None:
        """Build canonical pages.jsonl from native text blocks.

        Args:
            source_id: The source ID.
            native_blocks: Extracted text blocks.
            append: If True, append to existing files. If False, overwrite.
        """
        pages: dict[int, ExtractedPage] = {}

        for blk in native_blocks:
            page_num = blk.page_number
            if page_num not in pages:
                pages[page_num] = ExtractedPage(
                    source_id=source_id,
                    page_number=page_num,
                    image_path=f"pages/page_{page_num:04d}.pdf",
                    markdown="",
                    blocks=[],
                    image_asset_ids=[],
                )

            block_id = f"p{page_num:04d}_b{blk.block_index:03d}"
            page_block = PageBlock(
                id=block_id,
                page_number=page_num,
                block_type=blk.block_type,
                text=blk.text,
                reading_order=blk.block_index,
                confidence=1.0,
            )
            pages[page_num].blocks.append(page_block)

        for page_num in sorted(pages.keys()):
            pages[page_num].markdown = self._blocks_to_markdown(
                pages[page_num].blocks
            )

        extracted_pages = [pages[n] for n in sorted(pages.keys())]
        self._save_pages_jsonl(source_id, extracted_pages, append=append)

        logger.info(
            "build_from_native_text: source=%s pages=%d append=%s",
            source_id,
            len(extracted_pages),
            append,
        )

    def rebuild_book_md(self, source_id: str) -> None:
        """Rebuild book.md from all pages in pages.jsonl."""
        pages_path = self._storage.get_canonical_dir(source_id) / "pages.jsonl"
        records = self._storage.load_jsonl(pages_path)

        pages: list[ExtractedPage] = []
        for record in records:
            pages.append(ExtractedPage.model_validate(record))

        pages.sort(key=lambda p: p.page_number)
        book_md = self._pages_to_book_markdown(pages)
        self._storage.save_text(
            self._storage.get_canonical_dir(source_id) / "book.md",
            book_md,
        )

        logger.info(
            "rebuild_book_md: source=%s pages=%d book_len=%d",
            source_id,
            len(pages),
            len(book_md),
        )

    def _blocks_to_markdown(self, blocks: list[PageBlock]) -> str:
        """Convert ordered blocks to Markdown text."""
        parts: list[str] = []
        for blk in blocks:
            if blk.text is None:
                continue
            if blk.block_type == "heading":
                parts.append(f"\n## {blk.text}\n")
            else:
                parts.append(f"{blk.text}\n")
        return "\n".join(parts).strip()

    def _pages_to_book_markdown(self, pages: list[ExtractedPage]) -> str:
        """Concatenate all page markdown into a single book document."""
        sections: list[str] = []
        for page in pages:
            header = f"\n---\n\n# Page {page.page_number}\n\n"
            sections.append(header + page.markdown)
        return "\n".join(sections)

    def _save_pages_jsonl(
        self,
        source_id: str,
        pages: list[ExtractedPage],
        *,
        append: bool = True,
    ) -> None:
        records = [page.model_dump() for page in pages]
        output = self._storage.get_canonical_dir(source_id) / "pages.jsonl"
        if not append and output.exists():
            output.unlink()
        self._storage.save_jsonl(output, records)
