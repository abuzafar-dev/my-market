from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Bildirishnomalar (WhatsApp)"

    def ready(self):
        # Hooks the debt ledger and customer saves; the debt app itself never
        # imports anything from here.
        from . import checks, signals  # noqa: F401
