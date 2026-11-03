"""WhatsApp debt notifications: consent, per-shop settings and the message log.

The one rule everything here serves: a customer gets a business-initiated
message only while an active WhatsAppConsent exists for exactly the number the
message goes to — checked again at the moment of sending, not only when the
message was queued (see services.deliver).
"""

from datetime import time

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import BaseModel
from apps.debt.models import Customer, DebtEntry
from apps.shops.models import Shop, User


class WhatsAppConsent(BaseModel):
    """The customer's current permission to be messaged on one number.

    One row per customer; every change is also written to ConsentEvent, which
    is the audit trail (who recorded it, when, from where). A phone in the
    customer card is never consent by itself — only a row with is_active=True
    whose ``phone`` still equals the customer's current number is."""

    class RevokeReason(models.TextChoices):
        CUSTOMER_STOP = "customer_stop", "Mijoz STOP yozdi"
        STAFF = "staff", "Do'kon xodimi o'chirdi"
        PHONE_CHANGED = "phone_changed", "Telefon raqami o'zgardi"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="whatsapp_consents", verbose_name="Do'kon"
    )
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="whatsapp_consent",
        verbose_name="Mijoz",
    )
    # E.164, e.g. +998901234567 — see phone.to_e164.
    phone = models.CharField(max_length=16, verbose_name="Telefon (E.164)")
    is_active = models.BooleanField(default=False, verbose_name="Faol")
    granted_at = models.DateTimeField(null=True, blank=True, verbose_name="Rozilik vaqti")
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Kim yozib qo'ydi",
    )
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Bekor qilingan vaqti")
    revoke_reason = models.CharField(
        max_length=20, choices=RevokeReason.choices, blank=True, verbose_name="Bekor sababi"
    )

    class Meta:
        verbose_name = "WhatsApp rozilik"
        verbose_name_plural = "WhatsApp roziliklar"
        indexes = [models.Index(fields=["phone", "is_active"])]

    def __str__(self) -> str:
        return f"{self.customer} — {'faol' if self.is_active else 'faol emas'}"


class ConsentEvent(BaseModel):
    """Append-only history of every consent change."""

    class Action(models.TextChoices):
        GRANTED = "granted", "Rozilik berildi"
        REVOKED = "revoked", "Bekor qilindi"
        RESTORED = "restored", "Qayta yoqildi (START)"

    class Source(models.TextChoices):
        STAFF = "staff", "Do'kon xodimi"
        WHATSAPP = "whatsapp", "Mijoz WhatsApp orqali"
        SYSTEM = "system", "Tizim"

    consent = models.ForeignKey(
        WhatsAppConsent, on_delete=models.CASCADE, related_name="events", verbose_name="Rozilik"
    )
    action = models.CharField(max_length=10, choices=Action.choices, verbose_name="Amal")
    source = models.CharField(max_length=10, choices=Source.choices, verbose_name="Manba")
    phone = models.CharField(max_length=16, verbose_name="Telefon (E.164)")
    reason = models.CharField(max_length=20, blank=True, verbose_name="Sabab")
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Kim",
    )

    class Meta:
        verbose_name = "Rozilik tarixi"
        verbose_name_plural = "Rozilik tarixi"
        ordering = ["-created_at"]


def _default_window_start() -> time:
    return time(9, 0)


def _default_window_end() -> time:
    return time(20, 0)


class ShopNotificationSettings(models.Model):
    """Per-shop switches. Off by default: a shop starts messaging its
    customers only once the owner turns it on."""

    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="notification_settings",
        verbose_name="Do'kon",
    )
    enabled = models.BooleanField(default=False, verbose_name="WhatsApp xabarlari yoqilgan")
    reminder_days_before = models.PositiveSmallIntegerField(
        default=1,
        validators=[MaxValueValidator(7)],
        verbose_name="Muddatdan necha kun oldin eslatish",
    )
    # Business-initiated messages go out only between these local
    # (settings.TIME_ZONE, Asia/Tashkent) times; anything outside waits.
    send_window_start = models.TimeField(
        default=_default_window_start, verbose_name="Xabar yuborish boshlanishi"
    )
    send_window_end = models.TimeField(
        default=_default_window_end, verbose_name="Xabar yuborish tugashi"
    )
    # TZ FT-3 asks for one reminder once the term has passed. Repeating it
    # every N days is an opt-in beyond the TZ: 0 (the default) = never.
    overdue_repeat_days = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(30)],
        verbose_name="Muddat o'tgach har necha kunda qayta eslatish (0 — yo'q)",
    )
    max_reminders_per_debt = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Bitta qarz uchun eng ko'p eslatma",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bildirishnoma sozlamasi"
        verbose_name_plural = "Bildirishnoma sozlamalari"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(send_window_start__lt=models.F("send_window_end")),
                name="notif_window_start_before_end",
            ),
            models.CheckConstraint(
                condition=models.Q(reminder_days_before__lte=7),
                name="notif_days_before_max_7",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.shop} — bildirishnomalar"

    def clean(self):
        if self.send_window_start >= self.send_window_end:
            raise ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")

    @classmethod
    def for_shop(cls, shop_id) -> ShopNotificationSettings:
        settings, _ = cls.objects.get_or_create(shop_id=shop_id)
        return settings


class OutboundMessage(BaseModel):
    """One logical message to a customer — the unit of idempotency.

    ``idempotency_key`` is unique, so the same event (a retried Celery task, a
    webhook delivered twice, two workers running the same schedule) can only
    ever produce one row, and a row is sent at most once: it is claimed
    (QUEUED -> SENDING) by a conditional UPDATE before the API is called."""

    class Kind(models.TextChoices):
        DEBT_ADDED = "debt_added", "Qarz qo'shildi"
        DEBT_REMINDER = "debt_reminder", "Muddat eslatmasi"
        DEBT_OVERDUE = "debt_overdue", "Muddat o'tdi"
        PAYMENT_RECEIVED = "payment_received", "To'lov qabul qilindi"
        DEBT_CLOSED = "debt_closed", "Qarz yopildi"
        MANUAL_REMINDER = "manual_reminder", "Qo'lda eslatma"
        REPLY = "reply", "Bot javobi"

    class Status(models.TextChoices):
        QUEUED = "queued", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        DELIVERED = "delivered", "Yetkazildi"
        READ = "read", "O'qildi"
        FAILED = "failed", "Xatolik"
        # The request may have reached Meta but no answer came back (timeout,
        # dropped connection, worker died mid-call). Not retried — a second
        # debt message is worse than a missing one; an operator checks it.
        UNKNOWN = "unknown", "Natijasi noma'lum"
        # Never sent on purpose: consent withdrawn, debt paid off, shop turned
        # notifications off... The reason is in error_code.
        CANCELLED = "cancelled", "Bekor qilindi"

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_messages",
        verbose_name="Do'kon",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_messages",
        verbose_name="Mijoz",
    )
    # The ledger line this message is about (the first one, for an
    # aggregated "debt added"; the debt being reminded about...).
    debt_entry = models.ForeignKey(
        DebtEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbound_messages",
        verbose_name="Qarz yozuvi",
    )
    to_phone = models.CharField(max_length=16, verbose_name="Kimga (E.164)")
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="Turi")
    # Inputs needed to build the message at send time (entry ids, reply
    # text...), plus the template parameters actually sent, for the audit.
    params = models.JSONField(default=dict, blank=True, verbose_name="Parametrlar")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.QUEUED, verbose_name="Holati"
    )
    idempotency_key = models.CharField(max_length=120, unique=True, verbose_name="Kalit")
    external_id = models.CharField(
        max_length=128, blank=True, db_index=True, verbose_name="WhatsApp xabar ID"
    )
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Urinishlar")
    error_code = models.CharField(max_length=40, blank=True, verbose_name="Xato kodi")
    # A short, sanitised description — never the request, the token or the
    # customer's number.
    error_detail = models.CharField(max_length=255, blank=True, verbose_name="Xato tafsiloti")
    send_after = models.DateTimeField(verbose_name="Shu vaqtdan keyin yuborish")
    enqueued_at = models.DateTimeField(null=True, blank=True, verbose_name="Navbatga qo'yilgan")
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Yuborilgan")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Yetkazilgan")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="O'qilgan")
    failed_at = models.DateTimeField(null=True, blank=True, verbose_name="Xato vaqti")

    class Meta:
        verbose_name = "Chiquvchi xabar"
        verbose_name_plural = "Chiquvchi xabarlar"
        indexes = [
            models.Index(fields=["status", "send_after"]),
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["debt_entry", "kind"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.get_status_display()}"


class InboundMessage(BaseModel):
    """A message a customer sent to the shared business number."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Qabul qilindi"
        PROCESSING = "processing", "Ishlanmoqda"
        PROCESSED = "processed", "Ishlandi"
        FAILED = "failed", "Xatolik"

    wa_message_id = models.CharField(max_length=128, unique=True, verbose_name="WhatsApp ID")
    from_phone = models.CharField(max_length=16, verbose_name="Kimdan (E.164)")
    message_type = models.CharField(max_length=20, verbose_name="Turi")
    # Only what the bot needs to read a command: the text (truncated) or the
    # id of the button/list row pressed. Media and other content are not kept.
    text = models.CharField(max_length=512, blank=True, verbose_name="Matn")
    payload = models.CharField(max_length=128, blank=True, verbose_name="Tugma ID")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.RECEIVED, verbose_name="Holati"
    )
    received_at = models.DateTimeField(verbose_name="Qabul qilingan")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Ishlangan")

    class Meta:
        verbose_name = "Kiruvchi xabar"
        verbose_name_plural = "Kiruvchi xabarlar"
        indexes = [models.Index(fields=["from_phone", "-received_at"])]

    def __str__(self) -> str:
        return f"{self.message_type} — {self.get_status_display()}"
