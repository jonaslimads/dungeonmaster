import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from rag.config import settings

logger = logging.getLogger(__name__)

MAX_VLM_RETRIES = 5
VLM_RETRY_BASE_DELAY = 2.0


class VlmLayoutBlockDTO:
    __slots__ = ("block_type", "text", "bbox", "reading_order", "confidence")

    def __init__(
        self,
        *,
        block_type: str,
        text: str | None,
        bbox: list[float],
        reading_order: int,
        confidence: float,
    ) -> None:
        self.block_type = block_type
        self.text = text
        self.bbox = bbox
        self.reading_order = reading_order
        self.confidence = confidence


class VlmVisualAssetDTO:
    __slots__ = ("asset_type", "title", "description", "bbox", "linked_text", "useful_for_gameplay", "confidence")

    def __init__(
        self,
        *,
        asset_type: str,
        title: str | None,
        description: str,
        bbox: list[float],
        linked_text: str | None,
        useful_for_gameplay: bool,
        confidence: float,
    ) -> None:
        self.asset_type = asset_type
        self.title = title
        self.description = description
        self.bbox = bbox
        self.linked_text = linked_text
        self.useful_for_gameplay = useful_for_gameplay
        self.confidence = confidence


class VlmPageAnalysisDTO:
    __slots__ = ("page_number", "markdown", "layout_blocks", "visual_assets")

    def __init__(
        self,
        *,
        page_number: int,
        markdown: str,
        layout_blocks: list[VlmLayoutBlockDTO],
        visual_assets: list[VlmVisualAssetDTO],
    ) -> None:
        self.page_number = page_number
        self.markdown = markdown
        self.layout_blocks = layout_blocks
        self.visual_assets = visual_assets


_VLM_SYSTEM_PROMPT = (
    "You are a PDF layout analysis and OCR assistant for RPG rulebooks. "
    "Analyze the page image and return structured JSON.\n\n"
    "## Markdown Reconstruction (PRIMARY TASK)\n\n"
    "Reconstruct the full page as clean, well-structured Markdown.\n\n"
    "### Heading Hierarchy\n"
    "- **H1 (`#`)**: Chapter titles, major section titles (largest, boldest text on the page).\n"
    "- **H2 (`##`)**: Section titles within a chapter (large, prominent headings).\n"
    "- **H3 (`###`)**: Subsection titles, rule category headers (medium-sized headings).\n"
    "- **H4 (`####`)**: Sub-subsection titles, individual rule/feature names when they act as headers.\n"
    "- When in doubt about heading level, look at font size, weight, and capitalization.\n"
    "- A fully capitalized line that is larger than surrounding text is almost always a heading.\n"
    "- Do NOT flatten everything to the same level — use the visual hierarchy to decide.\n\n"
    "### Text Formatting\n"
    "- Use **bold** for emphasized terms, rule names, ability names, and key mechanics terms.\n"
    "- Use *italics* for flavor text, narrative descriptions, and spoken dialogue.\n"
    "- Use `inline code` for dice notation (e.g., `1d20 + 5`, `2d6+3`).\n"
    "- Use ~~strikethrough~~ only if the original text shows crossed-out content.\n"
    "- Use > blockquotes for sidebar text, callout boxes, or quoted material.\n"
    "- Use --- for horizontal rules that separate major sections on the page.\n\n"
    "### Lists and Tables\n"
    "- Convert tables to proper Markdown table format with | separators and header rows.\n"
    "- Use numbered lists (1. 2. 3.) for ordered steps, prerequisites, or sequences.\n"
    "- Use bullet lists (- or *) for unordered item collections, trait lists, option lists.\n"
    "- Use nested lists when the visual indentation shows sub-items.\n\n"
    "### Structural Rules\n"
    "- Keep paragraphs coherent — do NOT break words across lines.\n"
    "- Do NOT add line breaks in the middle of words or phrases.\n"
    "- Preserve special characters, numbers, and symbols accurately.\n"
    "- Page numbers at the bottom of pages should be omitted from the markdown.\n"
    "- DO NOT invent content. Only transcribe what is visible.\n\n"
    "### Domain-Specific Formatting\n"
    "- **Spell entries**: name as heading, then level, school, casting time, range, components, duration, description.\n"
    "- **Monster entries**: name as heading, then size/type, armor class, hit points, speed, ability scores, skills, senses, CR, traits, actions.\n"
    "- **Class features**: name as heading, then level, description.\n"
    "- **Stat blocks**: preserve as structured text with clear labeled fields.\n"
    "- **Rules**: preserve the exact wording and structure.\n\n"
    "## Layout Blocks\n\n"
    "For each text block on the page:\n"
    "- Return the block type: heading, subheading, body_text, caption, table, list, footnote, page_number, stat_block, spell_block, monster_block.\n"
    "- Extract the text as accurately as possible.\n"
    "- Provide a bounding box in [x1, y1, x2, y2] pixel coordinates.\n"
    "- Assign a reading_order integer.\n"
    "- Estimate confidence (0.0 to 1.0).\n\n"
    "## Visual Assets\n\n"
    "Detect all meaningful visual image regions on the page.\n\n"
    "For each visual region:\n"
    "- Return a bounding box in [x1, y1, x2, y2] pixel coordinates.\n"
    "- Classify the asset type: map, illustration, character_art, monster_art, item_art, "
    "symbol, diagram, table_image, stat_block_image, decorative_art, cover_art, unknown.\n"
    "- Describe what the image appears to show.\n"
    "- Say whether it is useful for gameplay.\n"
    "- Ignore purely decorative borders unless they contain useful information.\n"
    "- Prefer one bounding box per coherent visual asset.\n"
    "- If the image is a map, mention visible labels, room numbers, paths, or regions.\n"
    "- If the image is a monster, character, item, symbol, or diagram, describe it briefly.\n"
    "- Do not invent names unless the page text clearly supports them.\n\n"
    "## Output Format\n\n"
    "Return ONLY valid JSON with this structure:\n"
    '{\n'
    '  "markdown": "...",\n'
    '  "layout_blocks": [\n'
    '    {\n'
    '      "block_type": "...",\n'
    '      "text": "...",\n'
    '      "bbox": [x1, y1, x2, y2],\n'
    '      "reading_order": 0,\n'
    '      "confidence": 0.0\n'
    '    }\n'
    '  ],\n'
    '  "visual_assets": [\n'
    '    {\n'
    '      "asset_type": "...",\n'
    '      "title": "..." or null,\n'
    '      "description": "...",\n'
    '      "bbox": [x1, y1, x2, y2],\n'
    '      "linked_text": "..." or null,\n'
    '      "useful_for_gameplay": true or false,\n'
    '      "confidence": 0.0\n'
    '    }\n'
    '  ]\n'
    '}'
)


class VlmClient:
    def __init__(self, *, timeout_seconds: int = 120) -> None:
        self._base_url = settings.vlm_url.rstrip("/")
        self._password = settings.vlm_password
        self._model = settings.vlm_model
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        logger.info(
            "VlmClient: url=%s model=%s timeout=%ds",
            self._base_url,
            self._model,
            timeout_seconds,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        await self._http.aclose()

    async def analyze_page_layout(
        self,
        *,
        page_image_path: Path,
        page_number: int,
    ) -> VlmPageAnalysisDTO:
        """Send a page image to Gemma 4 for layout analysis, OCR, and visual asset detection."""
        t0 = time.monotonic()

        with open(page_image_path, "rb") as f:
            image_bytes = f.read()
        image_size_kb = len(image_bytes) / 1024
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        t_encode = time.monotonic() - t0
        logger.info(
            "analyze_page_layout: page=%d image=%0.1fKB encode=%0.2fs",
            page_number,
            image_size_kb,
            t_encode,
        )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _VLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {
                            "type": "text",
                            "text": f"Analyze page {page_number}. Reconstruct the full markdown and detect all layout blocks and visual assets.",
                        },
                    ],
                },
            ],
            "max_tokens": 16384,
            "temperature": 0.1,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        url = f"{self._base_url}/chat/completions"
        logger.info(
            "analyze_page_layout: page=%d sending POST %s",
            page_number,
            url,
        )

        response = await self._request_with_retry(
            url,
            payload,
            headers,
            page_number,
        )

        logger.info(
            "analyze_page_layout: page=%d HTTP response status=%d",
            page_number,
            response.status_code,
        )

        if response.status_code >= 400:
            logger.error(
                "analyze_page_layout ERROR_RESPONSE: page=%d status=%d body=%s",
                page_number,
                response.status_code,
                response.text[:1000],
            )
            raise RuntimeError(f"VLM returned {response.status_code}: {response.text[:500]}")

        raw = response.json()
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")

        parsed = self._parse_vlm_response(content, page_number)
        t_total = time.monotonic() - t0
        logger.info(
            "analyze_page_layout OK: page=%d blocks=%d assets=%d markdown_len=%d total=%0.2fs (encode=%0.2fs)",
            page_number,
            len(parsed.layout_blocks),
            len(parsed.visual_assets),
            len(parsed.markdown),
            t_total,
            t_encode,
        )
        return parsed

    def _parse_vlm_response(
        self,
        content: str,
        page_number: int,
    ) -> VlmPageAnalysisDTO:
        """Parse the JSON response from the VLM."""
        json_str = self._extract_json(content)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(
                "VlmClient _parse_vlm_response JSON error on page %d: %s",
                page_number,
                exc,
            )
            return VlmPageAnalysisDTO(
                page_number=page_number,
                markdown=content,
                layout_blocks=[],
                visual_assets=[],
            )

        layout_blocks: list[VlmLayoutBlockDTO] = []
        for blk in data.get("layout_blocks", []):
            layout_blocks.append(
                VlmLayoutBlockDTO(
                    block_type=blk.get("block_type", "body_text"),
                    text=blk.get("text"),
                    bbox=blk.get("bbox", [0, 0, 0, 0]),
                    reading_order=blk.get("reading_order", 0),
                    confidence=float(blk.get("confidence", 0.5)),
                )
            )

        visual_assets: list[VlmVisualAssetDTO] = []
        for asset in data.get("visual_assets", []):
            visual_assets.append(
                VlmVisualAssetDTO(
                    asset_type=asset.get("asset_type", "unknown"),
                    title=asset.get("title"),
                    description=asset.get("description", ""),
                    bbox=asset.get("bbox", [0, 0, 0, 0]),
                    linked_text=asset.get("linked_text"),
                    useful_for_gameplay=bool(asset.get("useful_for_gameplay", False)),
                    confidence=float(asset.get("confidence", 0.5)),
                )
            )

        return VlmPageAnalysisDTO(
            page_number=page_number,
            markdown=data.get("markdown", ""),
            layout_blocks=layout_blocks,
            visual_assets=visual_assets,
        )

    async def _request_with_retry(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str],
        page_number: int,
    ) -> httpx.Response:
        """Send HTTP request with exponential backoff for 429 rate limits."""
        last_error: Exception | None = None

        for attempt in range(MAX_VLM_RETRIES + 1):
            t0 = time.monotonic()
            try:
                response = await self._http.post(
                    url,
                    json=payload,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                elapsed = time.monotonic() - t0
                logger.error(
                    "analyze_page_layout TIMEOUT: page=%d attempt=%d elapsed=%0.2fs error=%s",
                    page_number,
                    attempt,
                    elapsed,
                    exc,
                )
                raise RuntimeError(
                    f"VLM request timed out for page {page_number}"
                ) from exc
            except httpx.RequestError as exc:
                elapsed = time.monotonic() - t0
                logger.error(
                    "analyze_page_layout REQUEST_ERROR: page=%d attempt=%d elapsed=%0.2fs error=%s",
                    page_number,
                    attempt,
                    elapsed,
                    exc,
                )
                raise RuntimeError(
                    f"VLM request failed for page {page_number}"
                ) from exc

            if response.status_code != 429:
                return response

            last_error = RuntimeError(
                f"VLM returned {response.status_code}: {response.text[:500]}"
            )

            retry_after = float(
                response.headers.get("Retry-After", VLM_RETRY_BASE_DELAY * 2 ** attempt)
            )
            logger.warning(
                "analyze_page_layout RATE_LIMIT: page=%d attempt=%d/%d "
                "retry_after=%0.1fs status=%d",
                page_number,
                attempt + 1,
                MAX_VLM_RETRIES,
                retry_after,
                response.status_code,
            )
            await asyncio.sleep(retry_after)

        logger.error(
            "analyze_page_layout EXHAUSTED_RETRIES: page=%d after %d attempts",
            page_number,
            MAX_VLM_RETRIES + 1,
        )
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text that may contain markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end]).strip()
        return text
