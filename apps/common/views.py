import time

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

from apps.common.tasks import HEARTBEAT_KEY

# Beat schedules the heartbeat every 60 s; three missed beats mean it is down.
HEARTBEAT_MAX_AGE = 180


def healthz(request):
    """GET /healthz/ — is the app up and can it reach its database?

    For uptime monitors and container health checks; no auth, no data."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})


def celery_healthz(request):
    """GET /healthz/celery/ — are celery beat and a worker running?

    200 while the last heartbeat (apps.common.tasks.beat_heartbeat) is at most
    HEARTBEAT_MAX_AGE seconds old, 503 otherwise. For an uptime monitor; no
    auth, no data. Kept apart from /healthz/ so a stopped worker does not
    make Docker restart the web container."""
    try:
        last = cache.get(HEARTBEAT_KEY)
    except Exception:  # Redis down: the broker is down too
        return JsonResponse({"status": "error"}, status=503)
    if last is None:
        return JsonResponse({"status": "missing"}, status=503)
    age = int(time.time() - last)
    if age > HEARTBEAT_MAX_AGE:
        return JsonResponse({"status": "stale", "beat_age": age}, status=503)
    return JsonResponse({"status": "ok", "beat_age": age})
