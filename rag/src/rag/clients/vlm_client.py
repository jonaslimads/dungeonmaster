import json
import logging
from pathlib import Path
from typing import Any

import httpx

from rag.config import settings

logger = logging.getLogger(__name__)


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


class VlmClient:
    def __init__(self, *, timeout_seconds: int = 300) -> None:
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
        system_prompt = (
            "You are a PDF layout analysis assistant. Analyze the page image and return structured JSON.\n\n"
            "For each text block on the page:\n"
            "- Return the block type (heading, body_text, caption, table, list, footnote, page_number).\n"
            "- Extract the text as accurately as possible.\n"
            "- Provide a bounding box in [x1, y1, x2, y2] pixel coordinates.\n"
            "- Assign a reading_order integer.\n"
            "- Estimate confidence (0.0 to 1.0).\n\n"
            "Also detect all meaningful visual image regions on the page.\n\n"
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
            "Also reconstruct the full page as clean Markdown.\n\n"
            "Return ONLY valid JSON with this structure:\n"
            '{\n'
            '  "markdown": "...",\n'
            '  "layout_blocks": [...],\n'
            '  "visual_assets": [...]\n'
            '}'
        )

        with open(page_image_path, "rb") as f:
            image_bytes = f.read()

        files = [
            ("file", ("page.png", image_bytes, "image/png")),
        ]
        data = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze page {page_number}."},
            ],
            "max_tokens": 8192,
            "temperature": 0.1,
        }

        logger.info(
            "analyze_page_layout: POST %s/chat/completions model=%s page=%d",
            self._base_url,
            self._model,
            page_number,
        )

        headers: dict[str, str] = {}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        try:
            response = await self._http.post(
                f"{self._base_url}/chat/completions",
                data=data,
                files=files,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            logger.error(
                "analyze_page_layout TIMEOUT: page=%d error=%s",
                page_number,
                exc,
            )
            raise RuntimeError(f"VLM request timed out for page {page_number}") from exc
        except httpx.RequestError as exc:
            logger.error(
                "analyze_page_layout REQUEST_ERROR: page=%d error=%s",
                page_number,
                exc,
            )
            raise RuntimeError(f"VLM request failed for page {page_number}") from exc

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
        logger.info(
            "analyze_page_layout OK: page=%d blocks=%d assets=%d",
            page_number,
            len(parsed.layout_blocks),
            len(parsed.visual_assets),
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
