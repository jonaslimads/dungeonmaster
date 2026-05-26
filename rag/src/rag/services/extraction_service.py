import asyncio
import logging
import uuid

from rag.models.extraction_job import ExtractionJob
from rag.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


class ExtractionService:
    """Manage extraction jobs and trigger the ingestion pipeline."""

    def __init__(self) -> None:
        self._ingestion = IngestionService()
        self._jobs: dict[str, ExtractionJob] = {}

    def create_job(
        self,
        *,
        source_id: str,
        use_vlm: bool = False,
        force: bool = False,
        offset: int = 0,
        limit: int = 0,
        batch_size: int = 10,
    ) -> ExtractionJob:
        """Create a new extraction job."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = ExtractionJob(
            id=job_id,
            source_id=source_id,
            status="pending",
            progress={
                "_use_vlm": use_vlm,
                "_force": force,
                "_offset": offset,
                "_limit": limit,
                "_batch_size": batch_size,
                "pages_rendered": False,
                "native_text_extracted": False,
                "vlm_layout_analyzed": False,
                "assets_cropped": False,
                "markdown_built": False,
                "quality_report_generated": False,
            },
        )
        self._jobs[job_id] = job
        logger.info(
            "create_job: job=%s source=%s use_vlm=%s force=%s offset=%d limit=%d batch_size=%d",
            job_id,
            source_id,
            use_vlm,
            force,
            offset,
            limit,
            batch_size,
        )
        return job

    async def run_job(self, job_id: str) -> ExtractionJob:
        """Start an extraction job in the background and return immediately."""
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        job.status = "running"
        logger.info("run_job: job=%s started (background)", job_id)
        asyncio.create_task(self._execute_job(job_id))
        return job

    async def _execute_job(self, job_id: str) -> None:
        """Execute the extraction pipeline in the background."""
        job = self._jobs.get(job_id)
        if job is None:
            return

        progress = job.progress or {}

        try:
            from pathlib import Path
            from rag.clients.storage_client import StorageClient

            pdf_path = Path(
                StorageClient.get_original_dir(job.source_id) / "source.pdf"
            )
            if not pdf_path.exists():
                raise FileNotFoundError(f"Source PDF not found: {pdf_path}")

            await self._ingestion.run_pipeline(
                source_id=job.source_id,
                pdf_path=pdf_path,
                use_vlm=progress.get("_use_vlm", False),
                force=progress.get("_force", False),
                offset=progress.get("_offset", 0),
                limit=progress.get("_limit", 0),
                batch_size=progress.get("_batch_size", 10),
            )

            progress.update({
                "pages_rendered": True,
                "native_text_extracted": True,
                "vlm_layout_analyzed": progress.get("_use_vlm", False),
                "assets_cropped": True,
                "markdown_built": True,
                "quality_report_generated": True,
            })
            job.status = "completed"
            job.progress = progress
            logger.info("run_job: job=%s completed", job_id)

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            logger.error("run_job: job=%s failed: %s", job_id, exc)

    def get_job(self, job_id: str) -> ExtractionJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)
