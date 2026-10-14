from rest_framework import serializers

from .models import ExportJob


class ExportJobSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = ("id", "kind", "status", "filename", "error", "download_url", "created_at")
        read_only_fields = fields

    def get_download_url(self, job: ExportJob) -> str | None:
        """The API path, not the storage URL.

        MEDIA is served straight off disk with no auth in front of it; a link
        to the file itself would let anyone with the path read another shop's
        takings. The download view checks the shop first.
        """
        if not job.is_downloadable:
            return None
        return f"/api/reports/export/{job.id}/download/"
