import logging

from rag.models.chunk import Chunk

logger = logging.getLogger(__name__)


class ChunkingService:
    """Placeholder for Phase 2 chunking pipeline.

    Will split book.md / pages.jsonl into parent and child chunks.
    """

    def chunk_document(
        self,
        *,
        source_id: str,
        markdown: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[Chunk]:
        logger.warning(
            "chunk_document: chunking not yet implemented for source=%s",
            source_id,
        )
        return []
