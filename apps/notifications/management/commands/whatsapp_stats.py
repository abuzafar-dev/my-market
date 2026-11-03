"""Message counts for monitoring (no customer data): queue depth, statuses,
failures by error code, template volume by kind."""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import stats


class Command(BaseCommand):
    help = "WhatsApp xabarlari statistikasi (navbat, holatlar, xatolar)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        self.stdout.write(json.dumps(stats(since), indent=2, default=str))
