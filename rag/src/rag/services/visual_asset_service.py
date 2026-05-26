import logging
from pathlib import Path

from rag.clients.storage_client import StorageClient
from rag.models.image_asset import BoundingBox, ImageAsset

logger = logging.getLogger(__name__)

MIN_ASSET_WIDTH = 30
MIN_ASSET_HEIGHT = 30


class VisualAssetService:
    def __init__(self) -> None:
        self._storage = StorageClient()

    def create_assets_from_vlm(
        self,
        *,
        source_id: str,
        page_number: int,
        page_width: int,
        page_height: int,
        vlm_assets: list[dict],
    ) -> list[ImageAsset]:
        """Convert VLM visual asset detections into validated ImageAsset models."""
        assets: list[ImageAsset] = []
        img_counter = 0

        for det in vlm_assets:
            bbox_data = det.get("bbox", [0, 0, 0, 0])
            bbox = BoundingBox(
                x1=float(bbox_data[0]),
                y1=float(bbox_data[1]),
                x2=float(bbox_data[2]),
                y2=float(bbox_data[3]),
            )

            if not self._is_valid_bbox(bbox, page_width, page_height):
                logger.warning(
                    "create_assets: invalid bbox on page %d, skipping",
                    page_number,
                )
                continue

            img_counter += 1
            asset_id = f"{source_id}_p{page_number:04d}_img_{img_counter:03d}"
            asset_type = det.get("asset_type", "unknown")
            description = det.get("description", "")

            image_path = f"assets/images/page_{page_number:04d}_img_{img_counter:03d}.png"

            asset = ImageAsset(
                id=asset_id,
                source_id=source_id,
                page_number=page_number,
                asset_type=asset_type,
                bbox=bbox,
                image_path=image_path,
                thumbnail_path=None,
                title=det.get("title"),
                description=description,
                useful_for_gameplay=bool(det.get("useful_for_gameplay", False)),
                linked_block_ids=det.get("linked_block_ids", []),
                confidence=float(det.get("confidence", 0.5)),
            )
            assets.append(asset)

        logger.info(
            "create_assets: source=%s page=%d detected=%d",
            source_id,
            page_number,
            len(assets),
        )
        return assets

    def save_assets(self, source_id: str, assets: list[ImageAsset]) -> None:
        """Save image asset metadata to image_assets.jsonl (overwrite)."""
        records = [asset.model_dump() for asset in assets]
        output = self._storage.get_extracted_dir(source_id) / "image_assets.jsonl"
        if output.exists():
            output.unlink()
        self._storage.save_jsonl(output, records)

    @staticmethod
    def _is_valid_bbox(bbox: BoundingBox, page_width: int, page_height: int) -> bool:
        """Validate that a bounding box is within page bounds and above minimum size."""
        if bbox.x2 <= bbox.x1 or bbox.y2 <= bbox.y1:
            return False
        width = bbox.x2 - bbox.x1
        height = bbox.y2 - bbox.y1
        if width < MIN_ASSET_WIDTH or height < MIN_ASSET_HEIGHT:
            return False
        if bbox.x1 < 0 or bbox.y1 < 0:
            return False
        if bbox.x2 > page_width or bbox.y2 > page_height:
            return False
        return True
