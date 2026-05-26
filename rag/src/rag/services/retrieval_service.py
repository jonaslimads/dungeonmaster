import math
from collections import Counter

from rag.clients.storage_client import StorageClient
from rag.models.chunk import Chunk

logger = __import__("logging").getLogger(__name__)


class RetrievalService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def search(
        self,
        *,
        query: str,
        source_ids: list[str] | None = None,
        chunk_types: list[str] | None = None,
        top_k: int = 8,
    ) -> list[dict]:
        """Search child chunks using TF-IDF scoring.

        Loads all child_chunks.jsonl from specified sources, scores each
        chunk against the query, and returns the top-k results with parent
        expansion.
        """
        chunks = self._load_chunks(source_ids)

        if chunk_types:
            chunks = [c for c in chunks if c.chunk_type in chunk_types]

        if not chunks:
            return []

        # Build vocabulary and IDF
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        chunk_texts = [self._tokenize(c.text) for c in chunks]
        idf = self._compute_idf(chunk_texts)

        # Score each chunk
        scored: list[tuple[float, Chunk]] = []
        for chunk, tokens in zip(chunks, chunk_texts):
            tf = Counter(tokens)
            score = self._tfidf_score(tf, query_terms, idf, len(tokens))
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: -x[0])
        top = scored[:top_k]

        # Expand to include parent info
        parent_map = self._load_parents(source_ids)
        results = []
        for score, chunk in top:
            parent = parent_map.get(chunk.parent_id or "")
            results.append({
                "chunk_id": chunk.id,
                "parent_id": chunk.parent_id,
                "title": chunk.title,
                "chunk_type": chunk.chunk_type,
                "source_id": chunk.source_id,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "score": round(score, 4),
                "text": chunk.text,
                "parent_text": parent.text if parent else None,
                "parent_title": parent.title if parent else None,
                "token_count": chunk.token_count,
            })

        logger.info(
            "search: query=%r sources=%s types=%s results=%d",
            query[:50],
            source_ids,
            chunk_types,
            len(results),
        )
        return results

    def _load_chunks(
        self,
        source_ids: list[str] | None,
    ) -> list[Chunk]:
        """Load all child chunks from specified sources."""
        if source_ids is None:
            source_ids = self._discover_sources()

        chunks: list[Chunk] = []
        for sid in source_ids:
            path = self._storage.get_source_dir(sid) / "chunks" / "child_chunks.jsonl"
            records = self._storage.load_jsonl(path)
            for record in records:
                chunks.append(Chunk.model_validate(record))
        return chunks

    def _load_parents(
        self,
        source_ids: list[str] | None,
    ) -> dict[str, Chunk]:
        """Load parent chunks into a map by ID."""
        if source_ids is None:
            source_ids = self._discover_sources()

        parent_map: dict[str, Chunk] = {}
        for sid in source_ids:
            path = self._storage.get_source_dir(sid) / "chunks" / "parent_chunks.jsonl"
            records = self._storage.load_jsonl(path)
            for record in records:
                chunk = Chunk.model_validate(record)
                parent_map[chunk.id] = chunk
        return parent_map

    def _discover_sources(self) -> list[str]:
        """Discover all source IDs from the filesystem."""
        sources_dir = self._storage.get_source_dir("")
        if not sources_dir.parent.exists():
            return []
        source_ids = []
        for entry in sorted(sources_dir.parent.iterdir()):
            if entry.is_dir():
                chunks_path = entry / "chunks" / "child_chunks.jsonl"
                if chunks_path.exists():
                    source_ids.append(entry.name)
        return source_ids

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        return [
            t.lower()
            for t in __import__("re").split(r"[^a-z0-9]+", text.lower())
            if len(t) > 1
        ]

    @staticmethod
    def _compute_idf(chunk_texts: list[list[str]]) -> dict[str, float]:
        """Compute inverse document frequency."""
        n_docs = len(chunk_texts)
        df: Counter = Counter()
        for tokens in chunk_texts:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] += 1

        return {
            term: math.log((n_docs + 1) / (freq + 1)) + 1
            for term, freq in df.items()
        }

    @staticmethod
    def _tfidf_score(
        tf: Counter,
        query_terms: list[str],
        idf: dict[str, float],
        doc_length: int,
    ) -> float:
        """Compute TF-IDF score for a document against a query."""
        if doc_length == 0:
            return 0.0

        score = 0.0
        query_counter = Counter(query_terms)
        for term, count in query_counter.items():
            tf_val = count / doc_length if doc_length > 0 else 0
            idf_val = idf.get(term, 1.0)
            score += tf_val * idf_val * count

        return score
