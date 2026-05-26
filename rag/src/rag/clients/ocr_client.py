import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from rag.config import settings

logger = logging.getLogger(__name__)


class OcrBlockDTO:
    __slots__ = ("text", "bbox", "confidence", "page_number")

    def __init__(
        self,
        *,
        text: str,
        bbox: list[float],
        confidence: float,
        page_number: int,
    ) -> None:
        self.text = text
        self.bbox = bbox
        self.confidence = confidence
        self.page_number = page_number


_OCR_SYSTEM_PROMPT = (
    "You are an OCR assistant. Extract all text from the page image.\n\n"
    "Return ONLY valid JSON with this structure:\n"
    '{\n'
    '  "blocks": [\n'
    '    {\n'
    '      "text": "extracted text",\n'
    '      "bbox": [x1, y1, x2, y2],\n'
    '      "confidence": 0.0\n'
    '    }\n'
    "  ]\n"
    "}\n\n"
    "- Extract text as accurately as possible.\n"
    "- Provide bounding boxes in [x1, y1, x2, y2] pixel coordinates.\n"
    "- Estimate confidence (0.0 to 1.0) for each block.\n"
    "- Group text into logical blocks (paragraphs, headings, lists).\n"
    "- Include ALL visible text, including small captions and footnotes."
)


class OcrClient:
    """OCR via Gemma 4 VLM — sends page images and extracts text blocks."""

    def __init__(self, *, timeout_seconds: int = 300) -> None:
        self._base_url = settings.vlm_url.rstrip("/")
        self._password = settings.vlm_password
        self._model = settings.vlm_model
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        logger.info(
            "OcrClient: url=%s model=%s timeout=%ds",
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

    async def extract_text_from_image(
        self,
        *,
        image_path: Path,
        page_number: int = 1,
    ) -> list[OcrBlockDTO]:
        """Send a page image to Gemma 4 for OCR text extraction."""
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {
                            "type": "text",
                            "text": f"Extract all text from page {page_number}.",
                        },
                    ],
                },
            ],
            "max_tokens": 8192,
            "temperature": 0.1,
        }

        logger.info(
            "extract_text_from_image: POST %s/chat/completions model=%s page=%d",
            self._base_url,
            self._model,
            page_number,
        )

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._password:
            headers["Authorization"] = f"Bearer {self._password}"

        try:
            response = await self._http.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            logger.error(
                "extract_text_from_image TIMEOUT: page=%d error=%s",
                page_number,
                exc,
            )
            raise RuntimeError(f"OCR request timed out for page {page_number}") from exc
        except httpx.RequestError as exc:
            logger.error(
                "extract_text_from_image REQUEST_ERROR: page=%d error=%s",
                page_number,
                exc,
            )
            raise RuntimeError(f"OCR request failed for page {page_number}") from exc

        if response.status_code >= 400:
            logger.error(
                "extract_text_from_image ERROR_RESPONSE: page=%d status=%d body=%s",
                page_number,
                response.status_code,
                response.text[:1000],
            )
            raise RuntimeError(f"OCR returned {response.status_code}: {response.text[:500]}")

        raw = response.json()
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")

        blocks = self._parse_ocr_response(content, page_number)
        logger.info(
            "extract_text_from_image OK: page=%d blocks=%d",
            page_number,
            len(blocks),
        )
        return blocks

    def _parse_ocr_response(
        self,
        content: str,
        page_number: int,
    ) -> list[OcrBlockDTO]:
        """Parse the JSON response from the VLM OCR."""
        json_str = self._extract_json(content)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(
                "OcrClient _parse_ocr_response JSON error on page %d: %s",
                page_number,
                exc,
            )
            return []

        blocks: list[OcrBlockDTO] = []
        for blk in data.get("blocks", []):
            blocks.append(
                OcrBlockDTO(
                    text=blk.get("text", ""),
                    bbox=blk.get("bbox", [0, 0, 0, 0]),
                    confidence=float(blk.get("confidence", 0.5)),
                    page_number=page_number,
                )
            )
        return blocks

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
