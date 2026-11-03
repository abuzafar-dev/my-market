from django.contrib import admin

from .models import (
    ConsentEvent,
    InboundMessage,
    OutboundMessage,
    ShopNotificationSettings,
    WhatsAppConsent,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """An audit trail: viewable, never edited or deleted by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WhatsAppConsent)
class WhatsAppConsentAdmin(ReadOnlyAdmin):
    list_display = ("customer", "shop", "is_active", "granted_at", "revoked_at", "revoke_reason")
    list_filter = ("is_active", "revoke_reason")


@admin.register(ConsentEvent)
class ConsentEventAdmin(ReadOnlyAdmin):
    list_display = ("consent", "action", "source", "reason", "actor", "created_at")
    list_filter = ("action", "source")


@admin.register(ShopNotificationSettings)
class ShopNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "shop",
        "enabled",
        "reminder_days_before",
        "send_window_start",
        "send_window_end",
        "max_reminders_per_debt",
        "overdue_repeat_days",
    )


@admin.register(OutboundMessage)
class OutboundMessageAdmin(ReadOnlyAdmin):
    list_display = ("kind", "status", "shop", "customer", "attempts", "error_code", "created_at")
    list_filter = ("status", "kind")
    exclude = ("params", "to_phone")  # financial details / number stay out of the admin list


@admin.register(InboundMessage)
class InboundMessageAdmin(ReadOnlyAdmin):
    list_display = ("message_type", "status", "received_at", "processed_at")
    list_filter = ("status", "message_type")
    exclude = ("text", "from_phone")
