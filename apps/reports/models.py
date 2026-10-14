"""Record of one requested export file.

The row is what the client polls and what the download is authorised against —
the Celery result backend is not, because it holds no shop and would let any
owner who guessed a task id read another shop's figures.
"""

from django.db import models

from apps.common.models import BaseModel
from apps.shops.models import Shop, User


def export_upload_to(instance: ExportJob, filename: str) -> str:
    # Per shop, so a misconfigured web server listing a directory still cannot
    # show one shop everything.
    return f"exports/{instance.shop_id}/{instance.pk}/{filename}"


class ExportJob(BaseModel):
    class Kind(models.TextChoices):
        PERIOD_XLSX = "period_xlsx", "Davr hisoboti (Excel)"

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        RUNNING = "running", "Tayyorlanmoqda"
        DONE = "done", "Tayyor"
        FAILED = "failed", "Xatolik"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="export_jobs", verbose_name="Do'kon"
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_jobs",
        verbose_name="Kim so'radi",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="Turi")
    # period / date / lang — what the task needs to rebuild the report.
    params = models.JSONField(default=dict, verbose_name="Parametrlar")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="Holati"
    )
    file = models.FileField(upload_to=export_upload_to, null=True, blank=True, verbose_name="Fayl")
    filename = models.CharField(max_length=255, blank=True, verbose_name="Fayl nomi")
    error = models.TextField(blank=True, verbose_name="Xatolik")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqti")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugagan vaqti")

    class Meta:
        verbose_name = "Eksport vazifasi"
        verbose_name_plural = "Eksport vazifalari"
        indexes = [models.Index(fields=["shop", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.get_status_display()}"

    @property
    def is_downloadable(self) -> bool:
        return self.status == self.Status.DONE and bool(self.file)
