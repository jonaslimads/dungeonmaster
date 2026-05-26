import logging
from pathlib import Path

import fitz
from PIL import Image

from rag.clients.storage_client import StorageClient
from rag.config import settings
from rag.models.image_asset import ImageAsset

logger = logging.getLogger(__name__)


class ImageCroppingService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def crop_and_save(
        self,
        *,
        source_id: str,
        asset: ImageAsset,
    ) -> ImageAsset:
        """Crop the detected region from the page (rendered in-memory from PDF) and save the asset + thumbnail."""
        from rag.clients.storage_client import StorageClient

        pdf_path = Path(
            StorageClient.get_original_dir(source_id) / "source.pdf"
        )
        if not pdf_path.exists():
            logger.error(
                "crop_and_save: source PDF not found: %s",
                pdf_path,
            )
            return asset

        images_dir = self._storage.get_assets_images_dir(source_id)
        thumbnails_dir = self._storage.get_assets_thumbnails_dir(source_id)

        try:
            doc = fitz.open(str(pdf_path))
            page = doc[asset.page_number - 1]
            scale = settings.page_render_dpi / 72.0
            matrix = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pix = None
            doc.close()
            x1 = int(asset.bbox.x1)
            y1 = int(asset.bbox.y1)
            x2 = int(asset.bbox.x2)
            y2 = int(asset.bbox.y2)

            cropped = img.crop((x1, y1, x2, y2))
            img.close()

            if cropped.width < 10 or cropped.height < 10:
                logger.warning(
                    "crop_and_save: cropped image too small for asset %s",
                    asset.id,
                )
                return asset

            image_path = images_dir / asset.image_path.split("/")[-1]
            cropped.save(str(image_path), "PNG")

            thumb_path = thumbnails_dir / f"{asset.id}.webp"
            thumb = cropped.copy()
            thumb.thumbnail((300, 300))
            thumb.save(str(thumb_path), "WEBP", quality=80)
            asset.thumbnail_path = f"assets/thumbnails/{asset.id}.webp"

            logger.info(
                "crop_and_save: asset=%s size=%dx%d",
                asset.id,
                cropped.width,
                cropped.height,
            )
        except Exception as exc:
            logger.error(
                "crop_and_save: failed for asset %s: %s",
                asset.id,
                exc,
            )

        return asset

    def crop_all(
        self,
        *,
        source_id: str,
        assets: list[ImageAsset],
    ) -> list[ImageAsset]:
        """Crop and save all assets for a source."""
        processed: list[ImageAsset] = []
        for asset in assets:
            processed.append(self.crop_and_save(source_id=source_id, asset=asset))
        logger.info(
            "crop_all: source=%s total=%d",
            source_id,
            len(processed),
        )
        return processed
