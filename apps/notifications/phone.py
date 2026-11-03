"""Phone numbers for messaging: strict E.164 for Uzbekistan, and masking for logs."""

import re

_UZ_E164 = re.compile(r"^\+998[1-9]\d{8}$")


def to_e164(raw: str | None) -> str | None:
    """Normalise "+998 90 123-45-67", "998901234567" or "901234567" to "+998901234567".

    Returns None for anything that is not a complete Uzbek number: a message
    must never go to a guess. (Login uses the more forgiving
    apps.shops.serializers.normalize_phone, which passes unknown input through.)"""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        digits = f"998{digits}"
    candidate = f"+{digits}"
    return candidate if _UZ_E164.match(candidate) else None


def mask(phone: str | None) -> str:
    """+998901234567 -> +99890*****67. The only form a number may take in a log."""
    if not phone:
        return "-"
    if len(phone) < 7:
        return "***"
    return f"{phone[:6]}{'*' * (len(phone) - 8)}{phone[-2:]}"
