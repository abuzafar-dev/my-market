from rest_framework import serializers

from . import services
from .models import OutboundMessage, ShopNotificationSettings


class OutboundMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundMessage
        fields = [
            "id",
            "kind",
            "status",
            "error_code",
            "send_after",
            "created_at",
            "sent_at",
            "delivered_at",
            "read_at",
        ]


class ConsentInputSerializer(serializers.Serializer):
    granted = serializers.BooleanField()


class ShopNotificationSettingsSerializer(serializers.ModelSerializer):
    whatsapp_configured = serializers.SerializerMethodField()

    class Meta:
        model = ShopNotificationSettings
        fields = [
            "enabled",
            "reminder_days_before",
            "send_window_start",
            "send_window_end",
            "max_reminders_per_debt",
            "overdue_repeat_days",
            "whatsapp_configured",
        ]
        extra_kwargs = {
            "reminder_days_before": {"min_value": 0, "max_value": 7},
            "max_reminders_per_debt": {"min_value": 1, "max_value": 10},
            "overdue_repeat_days": {"min_value": 0, "max_value": 30},
            "send_window_start": {"format": "%H:%M"},
            "send_window_end": {"format": "%H:%M"},
        }

    def get_whatsapp_configured(self, obj) -> bool:
        return services.channel_ready()

    def validate(self, attrs):
        start = attrs.get("send_window_start", getattr(self.instance, "send_window_start", None))
        end = attrs.get("send_window_end", getattr(self.instance, "send_window_end", None))
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"send_window_end": ["Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak."]}
            )
        return attrs
