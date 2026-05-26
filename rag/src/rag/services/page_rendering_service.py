import logging
from pathlib import Path

from rag.clients.pdf_client import PdfClient
from rag.clients.storage_client import StorageClient
from rag.config import settings

logger = logging.getLogger(__name__)


class PageRenderingService:
    def __init__(self) -> None:
        self._pdf = PdfClient(render_dpi=settings.page_render_dpi)
        self._storage = StorageClient()

    def render_pages(
        self,
        *,
        source_id: str,
        pdf_path: Path,
        page_range: range,
    ) -> list[Path]:
        """Render a range of pages from the PDF to PNG images."""
        pages_dir = self._storage.get_pages_dir(source_id)
        rendered: list[Path] = []

        for page_num in page_range:
            page_index = page_num - 1
            output = pages_dir / f"page_{page_num:04d}.png"
            self._pdf.render_page(pdf_path, page_index, output)
            rendered.append(output)

        logger.info(
            "render_pages: source=%s pages=%d-%d",
            source_id,
            page_range[0],
            page_range[-1],
        )
        return rendered
