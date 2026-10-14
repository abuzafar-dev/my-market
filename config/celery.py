"""Celery application.

Two kinds of work run here: WhatsApp notifications (apps/notifications —
sending, the per-minute sweeper, debt reminders; see docs/WHATSAPP.md), and
building the Excel report, which has to
assemble the whole workbook in memory before it can send a single byte. Doing
that inside the request kept a gunicorn worker busy for as long as it took, and
with a handful of workers a few owners exporting a month at once was enough to
stop the shop from selling. CSV is not affected — it streams row by row — so it
stays synchronous (see apps/reports/views.py).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("my_market")

# Every CELERY_* setting in Django's settings is a Celery setting here.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
