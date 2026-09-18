"""Wraps every DRF error response in the project's standard envelope.

TZ v2 section 8.1 fixes the shape of every API response:
success -> {"data": ..., "error": null}
failure -> {"data": null, "error": {"code": ..., "message": ...}}

Section 8.5 additionally expects field-level validation errors to be
reachable as `error.fields.<name>` so the frontend can show them under
the right input. DRF's default handler returns the field-errors dict
as the top-level body and a plain {"detail": ...} for everything else
(auth, permission, throttling, 404) — this re-shapes both into the one
envelope instead of leaking DRF's raw response format to every client.
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler

# DRF ships no "uz" locale (see rest_framework/locale/), so its generic
# exception messages render in English regardless of LANGUAGE_CODE.
# Django's own validators (required field, password rules, ...) are
# already translated via django/conf/locale/uz and don't need this.
_UZ_MESSAGES = {
    "not_authenticated": "Tizimga kirish talab qilinadi.",
    "authentication_failed": "Kirish ma'lumotlari noto'g'ri.",
    "permission_denied": "Bu amal uchun ruxsatingiz yo'q.",
    "not_found": "So'ralgan narsa topilmadi.",
    "method_not_allowed": "Bu amal ushbu manzilda qo'llab-quvvatlanmaydi.",
    "throttled": "Juda ko'p urinish qilindi. Birozdan so'ng qayta urinib ko'ring.",
    "parse_error": "So'rov ma'lumotlari noto'g'ri formatda.",
    "unsupported_media_type": "Qo'llab-quvvatlanmaydigan ma'lumot turi.",
    "not_acceptable": "So'ralgan format qo'llab-quvvatlanmaydi.",
}


def _first_message(value) -> str:
    if isinstance(value, list):
        return _first_message(value[0]) if value else ""
    if isinstance(value, dict):
        return _first_message(next(iter(value.values()), ""))
    return str(value)


def exception_handler(exc, context):
    # rest_framework.views.exception_handler does this same conversion
    # internally, but on its own local variable — our `exc` here would
    # otherwise stay a bare Http404/PermissionDenied with no default_code,
    # and the messages below key off of that code.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound(*exc.args)
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied(*exc.args)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    code = getattr(exc, "default_code", "error")

    if isinstance(detail, dict) and set(detail) == {"detail"}:
        fields = None
        message = _UZ_MESSAGES.get(code, str(detail["detail"]))
    elif isinstance(detail, dict):
        fields = {
            field: [str(item) for item in messages]
            if isinstance(messages, list)
            else [str(messages)]
            for field, messages in detail.items()
        }
        message = _first_message(detail)
        code = "validation_error"
    else:
        fields = None
        message = _first_message(detail)

    response.data = {"data": None, "error": {"code": code, "message": message, "fields": fields}}
    return response
