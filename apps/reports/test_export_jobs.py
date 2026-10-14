"""The background Excel export: job lifecycle, failure handling, and who may
download the finished file.

Tasks run eagerly here (CELERY_TASK_ALWAYS_EAGER in config/settings/test.py),
so no broker or worker is needed — the task writes the same job states either
way, which is what these assert.
"""

import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from celery.exceptions import Retry
from django.test import TestCase, override_settings
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Product
from apps.reports.models import ExportJob
from apps.reports.tasks import build_period_export, purge_expired_exports
from apps.sales.models import Sale
from apps.sales.services import CartLine, create_sale
from apps.shops.models import Shop, ShopSettings, User

MEDIA = tempfile.mkdtemp(prefix="my-market-test-media-")


@override_settings(MEDIA_ROOT=MEDIA)
class ExportJobTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Egasi",
        )
        self.seller = User.objects.create_user(
            phone="+998907778899",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Sotuvchi",
            role=User.Role.SELLER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Non",
            unit=Product.Unit.PIECE,
            markup_amount=500,
            min_stock=Decimal("5"),
        )
        Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=Decimal("20"),
            qty_remaining=Decimal("20"),
            cost_price=2000,
            sale_price=2500,
        )
        create_sale(
            shop=self.shop,
            user=self.owner,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("3"))],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def queue(self, **payload):
        """POST the export and let the on_commit hook fire.

        The view queues the task with transaction.on_commit, which never runs
        inside TestCase's own transaction — without this the job would sit at
        PENDING forever and these tests would prove nothing.
        """
        payload.setdefault("period", "month")
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/reports/export/", payload, format="json")


class QueueExportTests(ExportJobTestCase):
    def test_post_queues_a_job_and_returns_202(self):
        response = self.queue(lang="uz")

        self.assertEqual(response.status_code, 202)
        job = ExportJob.objects.get()
        self.assertEqual(str(job.id), response.data["id"])
        self.assertEqual(job.shop, self.shop)
        self.assertEqual(job.requested_by, self.owner)
        self.assertEqual(job.params["period"], "month")

    def test_the_task_produces_a_readable_workbook(self):
        self.queue()

        job = ExportJob.objects.get()
        self.assertEqual(job.status, ExportJob.Status.DONE)
        self.assertTrue(job.file)
        self.assertTrue(job.filename.endswith(".xlsx"))

        workbook = load_workbook(BytesIO(job.file.read()))
        # Summary, per-day, every sale, per-product.
        self.assertEqual(len(workbook.sheetnames), 4)

    def test_a_bad_date_is_rejected_before_anything_is_queued(self):
        response = self.queue(date="14-09-2026")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ExportJob.objects.exists())

    def test_a_seller_may_not_queue_an_export(self):
        self.client.force_authenticate(self.seller)

        response = self.queue()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ExportJob.objects.exists())

    def test_csv_still_comes_back_on_the_same_url(self):
        """CSV streams and stays synchronous — only the workbook moved."""
        response = self.client.get("/api/reports/export/?period=month")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])


class ExportJobStatusTests(ExportJobTestCase):
    def test_polling_reports_done_with_a_download_url(self):
        self.queue()
        job = ExportJob.objects.get()

        response = self.client.get(f"/api/reports/export/{job.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "done")
        self.assertEqual(response.data["download_url"], f"/api/reports/export/{job.id}/download/")

    def test_a_pending_job_has_no_download_url(self):
        job = ExportJob.objects.create(
            shop=self.shop, requested_by=self.owner, kind=ExportJob.Kind.PERIOD_XLSX, params={}
        )

        response = self.client.get(f"/api/reports/export/{job.id}/")

        self.assertEqual(response.data["status"], "pending")
        self.assertIsNone(response.data["download_url"])

    def test_downloading_returns_the_file(self):
        self.queue()
        job = ExportJob.objects.get()

        response = self.client.get(f"/api/reports/export/{job.id}/download/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(job.filename, response["Content-Disposition"])

    def test_downloading_an_unfinished_job_is_refused(self):
        job = ExportJob.objects.create(
            shop=self.shop, requested_by=self.owner, kind=ExportJob.Kind.PERIOD_XLSX, params={}
        )

        response = self.client.get(f"/api/reports/export/{job.id}/download/")

        self.assertEqual(response.status_code, 400)

    def test_an_unknown_id_is_404(self):
        response = self.client.get(f"/api/reports/export/{uuid4()}/")

        self.assertEqual(response.status_code, 404)


class ExportJobIsolationTests(ExportJobTestCase):
    """A finished export is a full set of one shop's takings. The file lives
    under MEDIA, which is served off disk with no auth, so the only thing
    standing between two shops is the view's shop check."""

    def setUp(self):
        super().setUp()
        self.other_shop = Shop.objects.create(name="Boshqa", phone="+998900000001")
        ShopSettings.objects.create(shop=self.other_shop)
        self.other_owner = User.objects.create_user(
            phone="+998905554433",
            password="pass1234",  # pragma: allowlist secret
            shop=self.other_shop,
            full_name="Boshqa egasi",
        )

    def test_another_shops_owner_cannot_see_the_job(self):
        self.queue()
        job = ExportJob.objects.get()

        self.client.force_authenticate(self.other_owner)
        response = self.client.get(f"/api/reports/export/{job.id}/")

        # 404, not 403: a 403 would confirm the id exists.
        self.assertEqual(response.status_code, 404)

    def test_another_shops_owner_cannot_download_the_file(self):
        self.queue()
        job = ExportJob.objects.get()

        self.client.force_authenticate(self.other_owner)
        response = self.client.get(f"/api/reports/export/{job.id}/download/")

        self.assertEqual(response.status_code, 404)


class ExportTaskTests(ExportJobTestCase):
    def test_a_job_already_done_is_not_rebuilt(self):
        """acks_late means a worker that dies after finishing sees the task
        again; rebuilding would attach a second file and lose the first."""
        self.queue()
        job = ExportJob.objects.get()
        first_name = job.file.name

        result = build_period_export(str(job.id))

        job.refresh_from_db()
        self.assertEqual(result, "already-done")
        self.assertEqual(job.file.name, first_name)

    def test_a_missing_job_does_not_raise(self):
        self.assertEqual(build_period_export(str(uuid4())), "missing")

    def _failing_job(self):
        return ExportJob.objects.create(
            shop=self.shop,
            requested_by=self.owner,
            kind=ExportJob.Kind.PERIOD_XLSX,
            params={"period": "month", "lang": "uz"},
        )

    def test_a_transient_failure_retries_and_leaves_the_job_pending(self):
        """The first failures ask Celery to try again; the job must go back to
        PENDING so the client keeps polling instead of showing an error."""
        job = self._failing_job()

        with patch(
            "apps.reports.tasks.period_xlsx_bytes", side_effect=RuntimeError("openpyxl boom")
        ):
            with self.assertRaises(Retry):
                build_period_export.apply(args=[str(job.id)], throw=True).get()

        job.refresh_from_db()
        self.assertEqual(job.status, ExportJob.Status.PENDING)

    def test_the_last_attempt_records_the_failure_on_the_job(self):
        """Once the retries are used up the job must say so, with a message the
        owner can read — not sit at RUNNING forever."""
        job = self._failing_job()

        with patch(
            "apps.reports.tasks.period_xlsx_bytes", side_effect=RuntimeError("openpyxl boom")
        ):
            with self.assertRaises(RuntimeError):
                # retries=2 == max_retries: this is the final attempt.
                build_period_export.apply(args=[str(job.id)], retries=2, throw=True).get()

        job.refresh_from_db()
        self.assertEqual(job.status, ExportJob.Status.FAILED)
        self.assertTrue(job.error)
        self.assertIsNotNone(job.finished_at)

    def test_purge_removes_old_jobs_and_their_files(self):
        self.queue()
        job = ExportJob.objects.get()
        path = job.file.path

        # Older than the retention window.
        ExportJob.objects.filter(pk=job.pk).update(created_at="2020-01-01T00:00:00Z")

        self.assertEqual(purge_expired_exports(), 1)
        self.assertFalse(ExportJob.objects.exists())
        import os

        self.assertFalse(os.path.exists(path))

    def test_purge_keeps_recent_jobs(self):
        self.queue()

        self.assertEqual(purge_expired_exports(), 0)
        self.assertEqual(ExportJob.objects.count(), 1)
