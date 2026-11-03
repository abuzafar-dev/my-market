"""Celery beat writes a heartbeat every minute; /healthz/celery/ turns 503 when
it stops. Beat is the process most likely to die unnoticed: the worker keeps
answering, but no Excel clean-up and no WhatsApp reminders are scheduled."""

from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase

from apps.common.tasks import HEARTBEAT_KEY, beat_heartbeat

NOW = 1_800_000_000.0


class CeleryHealthTests(TestCase):
    def setUp(self):
        cache.delete(HEARTBEAT_KEY)

    def heartbeat_at(self, when):
        with patch("time.time", return_value=when):
            beat_heartbeat()

    def get_at(self, when):
        with patch("time.time", return_value=when):
            return self.client.get("/healthz/celery/")

    def test_fresh_heartbeat_is_ok(self):
        self.heartbeat_at(NOW)

        response = self.get_at(NOW + 30)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "beat_age": 30})

    def test_heartbeat_at_the_limit_is_still_ok(self):
        self.heartbeat_at(NOW)

        self.assertEqual(self.get_at(NOW + 180).status_code, 200)

    def test_stale_heartbeat_is_503(self):
        self.heartbeat_at(NOW)

        response = self.get_at(NOW + 181)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "stale", "beat_age": 181})

    def test_missing_heartbeat_is_503(self):
        response = self.get_at(NOW)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "missing"})

    def test_cache_down_is_503_not_500(self):
        with patch("apps.common.views.cache.get", side_effect=ConnectionError("redis down")):
            response = self.get_at(NOW)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error"})

    def test_needs_no_login(self):
        self.heartbeat_at(NOW)

        self.assertNotIn(self.get_at(NOW).status_code, (401, 403))

    def test_heartbeat_is_scheduled_every_minute(self):
        entry = settings.CELERY_BEAT_SCHEDULE["beat-heartbeat"]

        self.assertEqual(entry["task"], "apps.common.tasks.beat_heartbeat")
        self.assertEqual(entry["schedule"], 60)

    def test_queued_heartbeats_expire(self):
        # After a worker outage a backlog of old heartbeats would keep the key
        # fresh even though beat itself has died; each one is only valid for
        # its own minute.
        entry = settings.CELERY_BEAT_SCHEDULE["beat-heartbeat"]

        self.assertEqual(entry["options"]["expires"], 60)
