# Importing the Celery app here is what makes @shared_task find it when Django
# starts, whether the process is a web worker, a Celery worker, or manage.py.
from .celery import app as celery_app

__all__ = ("celery_app",)
