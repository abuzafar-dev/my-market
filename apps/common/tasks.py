"""Housekeeping tasks shared by the whole project."""

import time

from celery import shared_task
from django.core.cache import cache

# Read by apps.common.views.celery_healthz.
HEARTBEAT_KEY = "celery:beat:last"


@shared_task(ignore_result=True)
def beat_heartbeat() -> None:
    """Scheduled every minute by celery beat (CELERY_BEAT_SCHEDULE). It runs
    on a worker, so a fresh value proves beat, the broker and a worker all
    work."""
    cache.set(HEARTBEAT_KEY, time.time(), timeout=None)
