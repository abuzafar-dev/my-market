"""Print the five Utility templates in Meta's submission format.

Prints only — nothing is sent to Meta. See docs/WHATSAPP.md for how to submit
them in WhatsApp Manager (or via the Graph API) and wait for approval.
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.templates import ALL_TEMPLATES


class Command(BaseCommand):
    help = "WhatsApp shablonlarini Meta'ga topshirish formatida chiqaradi (hech narsa yubormaydi)."

    def handle(self, *args, **options):
        language = settings.WHATSAPP_TEMPLATE_LANGUAGE
        definitions = [t.as_meta_definition(language) for t in ALL_TEMPLATES]
        self.stdout.write(json.dumps(definitions, ensure_ascii=False, indent=2))
