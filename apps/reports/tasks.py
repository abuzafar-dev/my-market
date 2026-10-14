"""Background work for reports.

The only reason any of this exists: the Excel report has to be fully built
before its first byte can be sent, so building it inside the request pinned a
gunicorn worker for the whole time. CSV streams and stays synchronous.
"""

import logging
from datetime import date, timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .exports import period_xlsx_bytes, period_xlsx_filename
from .models import ExportJob
from .services import period_bounds

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def build_period_export(self, job_id: str) -> str:
    """Build the workbook for one ExportJob and attach it to the row.

    Idempotent on purpose: acks_late means a worker that dies after finishing
    but before acknowledging will see this task again, and a job already marked
    DONE must not be rebuilt and re-saved under a second file.
    """
    job = ExportJob.objects.select_related("shop").filter(pk=job_id).first()
    if job is None:
        # The shop (and its jobs) was deleted while this sat in the queue.
        logger.warning("Export job %s no longer exists, nothing to build", job_id)
        return "missing"
    if job.status == ExportJob.Status.DONE:
        return "already-done"

    job.status = ExportJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        params = job.params or {}
        period = params.get("period", "month")
        lang = params.get("lang", "uz")
        anchor = date.fromisoformat(params["date"]) if params.get("date") else None
        start, end = period_bounds(period, anchor)

        content = period_xlsx_bytes(job.shop, period, start, end, lang)
        filename = period_xlsx_filename(lang, start, end)

        job.file.save(filename, ContentFile(content), save=False)
        job.filename = filename
        job.status = ExportJob.Status.DONE
        job.error = ""
        job.finished_at = timezone.now()
        job.save(update_fields=["file", "filename", "status", "error", "finished_at", "updated_at"])
        logger.info(
            "Export job %s finished for shop %s (%s bytes)", job.id, job.shop_id, len(content)
        )
        return "done"

    except SoftTimeLimitExceeded:
        # Past the time limit there is no point retrying with the same input.
        _fail(job, "Hisobot juda uzoq tayyorlandi va to'xtatildi.")
        raise

    except Exception as exc:  # noqa: BLE001 — the job records why, then re-raises
        logger.exception("Export job %s failed", job.id)
        if self.request.retries < self.max_retries:
            job.status = ExportJob.Status.PENDING
            job.save(update_fields=["status", "updated_at"])
            raise self.retry(exc=exc) from exc
        _fail(job, "Hisobotni tayyorlab bo'lmadi. Qaytadan urinib ko'ring.")
        raise


def _fail(job: ExportJob, message: str) -> None:
    job.status = ExportJob.Status.FAILED
    job.error = message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "finished_at", "updated_at"])


@shared_task
def purge_expired_exports() -> int:
    """Delete finished export files older than EXPORT_RETENTION_HOURS.

    These are full financial reports; they should not sit on disk indefinitely,
    and nobody downloads yesterday's generated file twice. Scheduled hourly by
    CELERY_BEAT_SCHEDULE.
    """
    cutoff = timezone.now() - timedelta(hours=settings.EXPORT_RETENTION_HOURS)
    removed = 0
    for job in ExportJob.objects.filter(created_at__lt=cutoff).iterator():
        if job.file:
            job.file.delete(save=False)
        job.delete()
        removed += 1
    if removed:
        logger.info("Purged %s expired export job(s)", removed)
    return removed
