"""Deployment checks for WhatsApp notifications (`manage.py check`)."""

from django.conf import settings
from django.core.checks import Warning, register

# Caches that live inside one process: the webhook, each Celery worker
# process and beat would each see their own copy.
PER_PROCESS_CACHES = {
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
}


@register()
def shared_cache_for_whatsapp(app_configs, **kwargs):
    """The bot keeps a customer's pending shop choice, the reply limit and
    the reminder-run lock in the cache. With a per-process cache the choice
    made in one worker process is invisible to the next (verified with two
    worker processes: the reply falls back to the help menu)."""
    if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
        return []
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if backend in PER_PROCESS_CACHES:
        return [
            Warning(
                "WhatsApp is configured but the default cache is per-process.",
                hint="Use the Redis cache (CACHE_URL / REDIS_URL) shared by the web "
                "process and every Celery worker, as config.settings.base does.",
                id="notifications.W001",
            )
        ]
    return []
