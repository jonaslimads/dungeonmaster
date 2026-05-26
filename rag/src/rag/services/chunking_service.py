import logging
import re
import uuid
from pathlib import Path

from rag.clients.storage_client import StorageClient
from rag.models.canonical_document import Section
from rag.models.chunk import Chunk

logger = logging.getLogger(__name__)

# Token estimation: ~4 chars per token for English/Portuguese text
CHARS_PER_TOKEN = 4

# Chunk size limits
PARENT_MIN_TOKENS = 200
PARENT_MAX_TOKENS = 6000
CHILD_MIN_TOKENS = 80
CHILD_MAX_TOKENS = 1200

# Known chunk types for classification
CHUNK_TYPES = (
    "rule",
    "spell",
    "class_feature",
    "monster",
    "item",
    "table",
    "section",
    "paragraph",
    "background",
    "feats",
    "equipment",
    "subrace",
    "unknown",
)


class ChunkingService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def chunk_source(
        self,
        *,
        source_id: str,
        force: bool = False,
    ) -> dict[str, int]:
        """Run the full chunking pipeline for a source.

        Reads book.md, parses sections, generates parent and child chunks,
        and saves to disk.
        """
        book_path = self._storage.get_canonical_dir(source_id) / "book.md"
        if not book_path.exists():
            raise FileNotFoundError(f"book.md not found for source: {source_id}")

        if not force:
            chunks_dir = self._storage.get_source_dir(source_id) / "chunks"
            parent_path = chunks_dir / "parent_chunks.jsonl"
            child_path = chunks_dir / "child_chunks.jsonl"
            if parent_path.exists() and child_path.exists():
                existing_parents = self._storage.load_jsonl(parent_path)
                existing_children = self._storage.load_jsonl(child_path)
                logger.info(
                    "chunk_source: source=%s already chunked (parents=%d, children=%d), skipping",
                    source_id,
                    len(existing_parents),
                    len(existing_children),
                )
                return {
                    "source_id": source_id,
                    "sections_count": 0,
                    "parent_chunks_count": len(existing_parents),
                    "child_chunks_count": len(existing_children),
                    "status": "skipped",
                }

        book_md = book_path.read_text(encoding="utf-8")

        # Step 1: Parse sections from book.md
        sections = self._parse_sections(source_id, book_md)
        self._save_sections(source_id, sections)
        logger.info("chunk_source: source=%s sections=%d", source_id, len(sections))

        # Step 2: Generate parent chunks (one per section)
        parent_chunks = self._build_parent_chunks(source_id, sections)
        self._save_chunks(source_id, "parent_chunks.jsonl", parent_chunks)
        logger.info("chunk_source: source=%s parents=%d", source_id, len(parent_chunks))

        # Step 3: Generate child chunks (split parents into smaller pieces)
        child_chunks = self._build_child_chunks(source_id, parent_chunks)
        self._save_chunks(source_id, "child_chunks.jsonl", child_chunks)
        logger.info("chunk_source: source=%s children=%d", source_id, len(child_chunks))

        # Step 4: Generate report
        report = self._generate_report(source_id, sections, parent_chunks, child_chunks)
        self._storage.save_text(
            self._storage.get_reports_dir(source_id) / "chunks_report.md",
            report,
        )

        return {
            "source_id": source_id,
            "sections_count": len(sections),
            "parent_chunks_count": len(parent_chunks),
            "child_chunks_count": len(child_chunks),
            "status": "completed",
        }

    def _parse_sections(
        self,
        source_id: str,
        book_md: str,
    ) -> list[Section]:
        """Parse book.md into sections based on Markdown headings."""
        lines = book_md.split("\n")
        sections: list[Section] = []
        current_heading = ""
        current_level = 0
        current_page: int | None = None
        current_lines: list[str] = []
        section_path: list[str] = []

        def flush_section() -> None:
            nonlocal current_heading, current_lines, current_page, current_level, section_path
            if not current_heading:
                return

            text = "\n".join(current_lines).strip()
            if not text:
                current_heading = ""
                current_lines = []
                return

            text_count = self._estimate_tokens(text)
            section_id = f"{source_id}_sec_{uuid.uuid4().hex[:8]}"

            sections.append(
                Section(
                    id=section_id,
                    source_id=source_id,
                    heading=current_heading,
                    level=current_level,
                    page_number=current_page,
                    text=text,
                    token_count=text_count,
                    section_path=list(section_path),
                )
            )
            current_heading = ""
            current_lines = []

        for line in lines:
            # Detect page markers: ---\n\n# Page N
            page_match = re.match(r"^#\s+Page\s+(\d+)", line.strip())
            if page_match:
                flush_section()
                current_page = int(page_match.group(1))
                continue

            # Detect headings: # or ## or ###
            heading_match = re.match(r"^(#+)\s+(.+)", line)
            if heading_match:
                flush_section()
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()

                # Build section path
                while section_path and level <= current_level:
                    section_path.pop()
                section_path.append(heading)

                current_heading = heading
                current_level = level
                continue

            current_lines.append(line)

        flush_section()
        return sections

    def _build_parent_chunks(
        self,
        source_id: str,
        sections: list[Section],
    ) -> list[Chunk]:
        """Build one parent chunk per section."""
        chunks: list[Chunk] = []

        for i, section in enumerate(sections):
            if section.token_count < PARENT_MIN_TOKENS:
                continue

            chunk_id = f"{source_id}_parent_{i:06d}"
            chunk_type = self._classify_chunk(section.heading, section.text, source_id)

            chunks.append(
                Chunk(
                    id=chunk_id,
                    source_id=source_id,
                    chunk_type=chunk_type,
                    title=section.heading,
                    text=section.text,
                    page_start=section.page_number,
                    page_end=section.page_number,
                    section_path=section.section_path,
                    token_count=section.token_count,
                )
            )

        return chunks

    def _build_child_chunks(
        self,
        source_id: str,
        parent_chunks: list[Chunk],
    ) -> list[Chunk]:
        """Split parent chunks into smaller child chunks."""
        children: list[Chunk] = []
        child_counter = 0

        for parent in parent_chunks:
            if parent.token_count <= CHILD_MAX_TOKENS:
                child_counter += 1
                children.append(
                    Chunk(
                        id=f"{source_id}_child_{child_counter:06d}",
                        source_id=source_id,
                        chunk_type=parent.chunk_type,
                        title=parent.title,
                        text=parent.text,
                        parent_id=parent.id,
                        page_start=parent.page_start,
                        page_end=parent.page_end,
                        section_path=parent.section_path,
                        token_count=parent.token_count,
                    )
                )
                continue

            sub_chunks = self._split_text(
                source_id=source_id,
                text=parent.text,
                title=parent.title,
                chunk_type=parent.chunk_type,
                parent_id=parent.id,
                section_path=parent.section_path,
                page_start=parent.page_start,
                page_end=parent.page_end,
            )
            for sub in sub_chunks:
                child_counter += 1
                sub.id = f"{source_id}_child_{child_counter:06d}"
                children.append(sub)

        return children

    def _split_text(
        self,
        *,
        source_id: str,
        text: str,
        title: str,
        chunk_type: str,
        parent_id: str,
        section_path: list[str],
        page_start: int | None,
        page_end: int | None,
    ) -> list[Chunk]:
        """Split a large text into child chunks, preserving semantic boundaries."""
        chunks: list[Chunk] = []

        # Try splitting on sub-headings first (## or ###)
        sub_sections = re.split(r"\n##\s+", text)

        if len(sub_sections) > 1:
            for sub_text in sub_sections:
                tokens = self._estimate_tokens(sub_text)
                if tokens >= CHILD_MIN_TOKENS:
                    chunks.append(
                        Chunk(
                            id="",
                            source_id=source_id,
                            chunk_type=chunk_type,
                            title=title,
                            text=sub_text.strip(),
                            parent_id=parent_id,
                            page_start=page_start,
                            page_end=page_end,
                            section_path=section_path,
                            token_count=tokens,
                        )
                    )
            return chunks

        # Split on double newlines (paragraphs)
        paragraphs = re.split(r"\n\s*\n", text)
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para.strip())
            if para_tokens == 0:
                continue

            if current_tokens + para_tokens > CHILD_MAX_TOKENS and current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(
                    Chunk(
                        id="",
                        source_id=source_id,
                        chunk_type=chunk_type,
                        title=title,
                        text=chunk_text.strip(),
                        parent_id=parent_id,
                        page_start=page_start,
                        page_end=page_end,
                        section_path=section_path,
                        token_count=current_tokens,
                    )
                )
                current_parts = [para.strip()]
                current_tokens = para_tokens
            else:
                current_parts.append(para.strip())
                current_tokens += para_tokens

        if current_parts:
            chunk_text = "\n\n".join(current_parts)
            if self._estimate_tokens(chunk_text) >= CHILD_MIN_TOKENS:
                chunks.append(
                    Chunk(
                        id="",
                        source_id=source_id,
                        chunk_type=chunk_type,
                        title=title,
                        text=chunk_text.strip(),
                        parent_id=parent_id,
                        page_start=page_start,
                        page_end=page_end,
                        section_path=section_path,
                        token_count=current_tokens,
                    )
                )

        return chunks

    @staticmethod
    def _classify_chunk(heading: str, text: str, source_id: str) -> str:
        """Classify chunk type using heuristics."""
        heading_lower = heading.lower()
        text_lower = text.lower()
        source_lower = source_id.lower()

        # Monster Manual heuristics
        if "monster" in source_lower:
            if re.search(r"challenge\s+rating|cr\s*:", text_lower):
                return "monster"
            if re.search(r"str\s*\d+\s*dex\s*\d+|ability\s+scores", text_lower):
                return "monster"

        # Spell patterns
        if any(kw in heading_lower for kw in ("spell", "magia", "cantrip")):
            return "spell"
        if re.search(r"level\s*\d+\s+(evocation|conjuration|illusion|necromancy|enchantment|abjuration|transmutation)", text_lower):
            return "spell"

        # Class features
        if any(kw in heading_lower for kw in ("class feature", "feature", "ability", "trait", "action surge", "second wind")):
            return "class_feature"

        # Equipment/items
        if any(kw in heading_lower for kw in ("weapon", "armor", "shield", "equipment", "item", "treasure")):
            return "item"
        if re.search(r"common|uncommon|rare|very rare|legendary|artifact", heading_lower):
            return "item"

        # Feats
        if "feat" in heading_lower or "dote" in heading_lower:
            return "feats"

        # Background
        if "background" in heading_lower or "antecedente" in heading_lower:
            return "background"

        # Tables
        if "|" in text and text.count("|") > 4:
            return "table"

        # Rules
        if any(kw in heading_lower for kw in ("rule", "regra", "combat", "fighting", "damage", "saving throw", "saving throws", "grapple", "stealth", "perception")):
            return "rule"

        # Subrace
        if any(kw in heading_lower for kw in ("subrace", "subraça", "variant")):
            return "subrace"

        # Default
        if len(heading) < 100:
            return "section"
        return "paragraph"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count from text length."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    def _save_sections(
        self,
        source_id: str,
        sections: list[Section],
    ) -> None:
        records = [s.model_dump() for s in sections]
        output = self._storage.get_canonical_dir(source_id) / "sections.jsonl"
        self._storage.save_jsonl(output, records)

    def _save_chunks(
        self,
        source_id: str,
        filename: str,
        chunks: list[Chunk],
    ) -> None:
        records = [c.model_dump() for c in chunks]
        chunks_dir = self._storage.get_source_dir(source_id) / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        output = chunks_dir / filename
        self._storage.save_jsonl(output, records)

    def _generate_report(
        self,
        source_id: str,
        sections: list[Section],
        parent_chunks: list[Chunk],
        child_chunks: list[Chunk],
    ) -> str:
        """Generate a chunking report."""
        type_counts: dict[str, int] = {}
        for chunk in child_chunks:
            ct = chunk.chunk_type
            type_counts[ct] = type_counts.get(ct, 0) + 1

        avg_tokens = 0
        if child_chunks:
            avg_tokens = sum(c.token_count for c in child_chunks) // len(child_chunks)

        lines = [
            f"# Chunking Report — {source_id}",
            "",
            "## Summary",
            f"- Sections: {len(sections)}",
            f"- Parent chunks: {len(parent_chunks)}",
            f"- Child chunks: {len(child_chunks)}",
            f"- Avg tokens per child: {avg_tokens}",
            "",
            "## Chunk types",
        ]

        for ct, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {ct}: {count}")

        lines.append("")
        return "\n".join(lines)
