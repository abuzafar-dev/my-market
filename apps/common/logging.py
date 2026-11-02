"""The current request's ID for log lines (set by RequestIdMiddleware)."""

import logging
from contextvars import ContextVar

# "-" outside a request: Celery tasks, management commands, start-up.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Adds ``record.request_id`` so the formatter can print ``[%(request_id)s]``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
