import uuid

from django.db import models


class BaseModel(models.Model):
    """Abstract base providing a UUID primary key and timestamps for every
    concrete model in the project."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
