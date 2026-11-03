"""WhatsApp webhook + the staff-facing notification endpoints."""

import hmac
import json
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import OuterRef, Subquery
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.permissions import IsOwner
from apps.debt.models import Customer
from apps.shops.models import User
from apps.shops.security import client_ip

from . import services
from .channels import get_channel
from .models import InboundMessage, OutboundMessage, ShopNotificationSettings, WhatsAppConsent
from .phone import to_e164
from .serializers import (
    ConsentInputSerializer,
    OutboundMessageSerializer,
    ShopNotificationSettingsSerializer,
)
from .tasks import apply_status_later, process_inbound_message

logger = logging.getLogger(__name__)

BAD_SIGNATURE_LIMIT, BAD_SIGNATURE_WINDOW = 30, 60
# Meta: "Webhook payloads can be up to 3 MB" (WhatsApp webhooks overview,
# checked 2026-10-13). Anything that is not a 200 is retried by Meta for up to
# 7 days, so a genuine payload must never be refused: 3 MiB plus headroom.
# Bigger bodies are refused before they are read or hashed. Django's global
# DATA_UPLOAD_MAX_MEMORY_SIZE (2.5 MB) would refuse them earlier, which is why
# the body is read from the stream below instead of request.body.
MAX_WEBHOOK_BODY = 4 * 1024 * 1024


# --------------------------------------------------------------------------
# Webhook — GET /api/whatsapp/webhook/ (verification), POST (events)
# --------------------------------------------------------------------------


def _bad_attempts_key(request) -> str:
    return f"whatsapp:bad-signature:{client_ip(request)}"


def _count_bad_attempt(request) -> int:
    key = _bad_attempts_key(request)
    cache.add(key, 0, BAD_SIGNATURE_WINDOW)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, BAD_SIGNATURE_WINDOW)
        return 1


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """Rate limiting here never touches a correctly signed request: Meta
    retries anything that is not a 2xx and may eventually disable the
    subscription, so a genuine delivery is always answered. What is limited:

    * unsigned / wrongly signed POSTs and wrong verify tokens, per client IP
      (403, then 429 once over BAD_SIGNATURE_LIMIT per minute) — the HMAC is
      still checked first, so even a flood from the proxy's own address (a
      misconfigured NUM_PROXIES) cannot lock Meta out;
    * bodies over MAX_WEBHOOK_BODY (413) — above Meta's documented 3 MB;
    * per customer, bot replies (bot.REPLY_LIMIT) — inside the worker, after
      the 200, so Meta's retry logic never sees it.
    """
    if request.method == "GET":
        return _verify(request)

    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > MAX_WEBHOOK_BODY:
        return HttpResponse(status=413)

    channel = get_channel()
    # Untouched bytes: the signature covers exactly these. Read from the
    # stream (bounded by Content-Length) so the app-wide 2.5 MB upload limit
    # does not apply here; the extra byte catches a body longer than declared.
    raw = request.read(MAX_WEBHOOK_BODY + 1)
    if len(raw) > MAX_WEBHOOK_BODY:
        return HttpResponse(status=413)
    if not channel.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        attempts = _count_bad_attempt(request)
        logger.warning("whatsapp webhook rejected: bad signature")
        return HttpResponse(status=429 if attempts > BAD_SIGNATURE_LIMIT else 403)

    try:
        payload = json.loads(raw)
    except ValueError:
        return HttpResponse(status=400)
    batch = channel.parse_webhook(payload)

    # Status updates are one indexed UPDATE each — cheap enough to apply here.
    for event in batch.statuses:
        if not services.apply_status(event):
            try:
                apply_status_later.apply_async(
                    (
                        {
                            "message_id": event.message_id,
                            "status": event.status,
                            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                            "error_code": event.error_code,
                            "error_title": event.error_title,
                        },
                    ),
                    countdown=60,
                )
            except Exception:  # noqa: BLE001 — unknown ids are mostly not ours
                pass

    pending = []
    for event in batch.messages:
        inbound = _store_inbound(event)
        if inbound.status == InboundMessage.Status.RECEIVED:
            pending.append(inbound.pk)
    try:
        for pk in pending:
            process_inbound_message.delay(str(pk))
    except Exception:  # noqa: BLE001
        # The messages are stored; a 503 makes Meta deliver the webhook again,
        # and the redelivery re-queues whatever is still unprocessed.
        logger.exception("whatsapp webhook: could not queue inbound processing")
        return HttpResponse(status=503)
    return HttpResponse("ok", content_type="text/plain")


def _verify(request):
    if cache.get(_bad_attempts_key(request), 0) >= BAD_SIGNATURE_LIMIT:
        return HttpResponse(status=429)
    expected = settings.WHATSAPP_VERIFY_TOKEN
    token = request.GET.get("hub.verify_token", "")
    if (
        expected
        and request.GET.get("hub.mode") == "subscribe"
        and hmac.compare_digest(token.encode(), expected.encode())
    ):
        return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
    _count_bad_attempt(request)
    return HttpResponse(status=403)


def _store_inbound(event) -> InboundMessage:
    defaults = {
        "from_phone": event.from_phone,
        "message_type": event.message_type,
        "text": event.text,
        "payload": event.payload,
        "received_at": event.timestamp or timezone.now(),
    }
    try:
        inbound, _ = InboundMessage.objects.get_or_create(
            wa_message_id=event.message_id, defaults=defaults
        )
    except IntegrityError:  # the same delivery processed concurrently
        inbound = InboundMessage.objects.get(wa_message_id=event.message_id)
    return inbound


# --------------------------------------------------------------------------
# Staff API
# --------------------------------------------------------------------------


class Rejected(APIException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, error: services.NotificationRejected):
        super().__init__(detail=error.message, code=error.code)
        self.default_code = error.code
        if error.code == "invalid_phone":
            self.status_code = status.HTTP_400_BAD_REQUEST


def _customer(request, pk) -> Customer:
    # Scoped to the caller's shop: another shop's customer is simply "not found".
    return get_object_or_404(Customer, pk=pk, shop=request.user.shop, is_active=True)


def _whatsapp_state(customer: Customer, user) -> dict:
    consent = WhatsAppConsent.objects.filter(customer=customer).select_related("granted_by").first()
    phone = to_e164(customer.phone)
    active = bool(consent and consent.is_active and consent.phone == phone)
    nsettings = ShopNotificationSettings.for_shop(customer.shop_id)
    configured = services.channel_ready()

    # One query: the latest status for each ledger line, for the history list.
    messages = list(
        OutboundMessage.objects.filter(customer=customer)
        .exclude(kind=OutboundMessage.Kind.REPLY)
        .order_by("-created_at")[:50]
    )
    entry_status = {}
    for message in messages:
        ids = message.params.get("entry_ids") or (
            [str(message.debt_entry_id)] if message.debt_entry_id else []
        )
        for entry_id in ids:
            entry_status.setdefault(
                entry_id,
                {"kind": message.kind, "status": message.status, "at": message.updated_at},
            )
    today = timezone.localdate().isoformat()
    # Today's, or one pressed late yesterday that goes out this morning /
    # one pressed tonight for tomorrow morning (keyed by delivery day).
    sent_today = any(
        m.kind == OutboundMessage.Kind.MANUAL_REMINDER
        and m.idempotency_key.rsplit(":", 1)[-1] >= today
        for m in messages
    )
    return {
        "configured": configured,
        "enabled": nsettings.enabled,
        "phone_valid": phone is not None,
        "consent": {
            "active": active,
            "phone": consent.phone,
            "granted_at": consent.granted_at,
            "granted_by_name": consent.granted_by.full_name if consent.granted_by else None,
            "revoked_at": consent.revoked_at,
            "revoke_reason": consent.revoke_reason,
        }
        if consent
        else None,
        "reminder_sent_today": sent_today,
        # TZ §3: the manual reminder is the owner's call; sellers see statuses.
        "can_remind": configured
        and user.role == User.Role.OWNER
        and nsettings.enabled
        and active
        and customer.debt_balance > 0
        and not sent_today,
        "last_message": OutboundMessageSerializer(messages[0]).data if messages else None,
        "entry_status": entry_status,
    }


class CustomerWhatsAppView(APIView):
    """GET /api/customers/<id>/whatsapp/ — consent + message statuses."""

    def get(self, request, pk):
        return Response(_whatsapp_state(_customer(request, pk), request.user))


class CustomerStatusesView(APIView):
    """GET /api/customers/whatsapp-statuses/?ids=<uuid>,<uuid>... — the latest
    message status of each listed customer, for the debt-book rows (FT-6).
    Only the caller's own shop's customers are ever looked at."""

    MAX_IDS = 200

    def get(self, request):
        ids = []
        for raw in request.query_params.get("ids", "").split(",")[: self.MAX_IDS]:
            try:
                ids.append(uuid.UUID(raw.strip()))
            except ValueError:
                continue
        latest = (
            OutboundMessage.objects.filter(customer=OuterRef("pk"))
            .exclude(kind=OutboundMessage.Kind.REPLY)
            .order_by("-created_at")
        )
        rows = (
            Customer.objects.filter(shop=request.user.shop, pk__in=ids)
            .annotate(
                wa_status=Subquery(latest.values("status")[:1]),
                wa_kind=Subquery(latest.values("kind")[:1]),
            )
            .exclude(wa_status=None)
            .values_list("pk", "wa_status", "wa_kind")
        )
        return Response({str(pk): {"status": st, "kind": kind} for pk, st, kind in rows})


class CustomerConsentView(APIView):
    """POST /api/customers/<id>/whatsapp-consent/ {"granted": true|false}

    Owners and sellers alike: it is recorded at the counter, with the customer."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "writes"

    def post(self, request, pk):
        customer = _customer(request, pk)
        serializer = ConsentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            if serializer.validated_data["granted"]:
                services.grant_consent(customer, request.user)
            else:
                services.revoke_consent(customer, request.user)
        except services.NotificationRejected as exc:
            raise Rejected(exc) from None
        return Response(_whatsapp_state(customer, request.user))


class SendReminderView(APIView):
    """POST /api/customers/<id>/send-reminder/ — "Eslatma yuborish". Owner
    only (TZ §3 roles: sellers record consent and see statuses)."""

    permission_classes = [IsAuthenticated, IsOwner]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reminders"

    def post(self, request, pk):
        customer = _customer(request, pk)
        try:
            message = services.send_manual_reminder(customer, request.user)
        except services.NotificationRejected as exc:
            raise Rejected(exc) from None
        return Response(OutboundMessageSerializer(message).data, status=status.HTTP_202_ACCEPTED)


class NotificationSettingsView(APIView):
    """GET/PATCH /api/shops/<id>/notification-settings/ — owner only, own shop only."""

    permission_classes = [IsAuthenticated, IsOwner]

    def _settings(self, request, shop_id) -> ShopNotificationSettings:
        if shop_id != request.user.shop_id:
            raise NotFound()
        return ShopNotificationSettings.for_shop(shop_id)

    def get(self, request, shop_id):
        return Response(ShopNotificationSettingsSerializer(self._settings(request, shop_id)).data)

    def patch(self, request, shop_id):
        serializer = ShopNotificationSettingsSerializer(
            self._settings(request, shop_id), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
