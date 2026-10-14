"""The five Utility templates and every text the bot sends, in Uzbek (Latin).

Template bodies here must match, word for word and variable for variable, what
is submitted to (and approved in) Meta WhatsApp Manager — `manage.py
whatsapp_templates` prints them in the submission format. Being defined here
says nothing about approval: a template that is not approved yet fails with
error 132001 and the message is recorded as failed, not retried.
"""

import re
from dataclasses import dataclass
from datetime import date

UNSUBSCRIBE_FOOTER = "Xabarlarni to'xtatish uchun STOP deb yozing."
BALANCE_BUTTON = "Qoldiqni ko'rish"
# What the quick-reply button sends back; the bot treats it like "qoldiq".
BALANCE_PAYLOAD = "BALANCE"
NO_DUE_DATE = "belgilanmagan"


@dataclass(frozen=True)
class TemplateDef:
    name: str
    body: str
    example: tuple[str, ...]

    def as_meta_definition(self, language: str) -> dict:
        return {
            "name": self.name,
            "category": "UTILITY",
            "language": language,
            "components": [
                {"type": "BODY", "text": self.body, "example": {"body_text": [list(self.example)]}},
                {"type": "FOOTER", "text": UNSUBSCRIBE_FOOTER},
                {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": BALANCE_BUTTON}]},
            ],
        }


DEBT_ADDED = TemplateDef(
    "debt_added",
    "Assalomu alaykum, {{1}}! {{2}} do'konida qarzingizga {{3}} so'm qo'shildi. "
    "Umumiy qarz: {{4}} so'm. To'lov muddati: {{5}}. "
    "Savollar bo'lsa, do'konga murojaat qiling.",
    ("Aziz", "Baraka", "50 000", "120 000", "20.10.2026"),
)
DEBT_REMINDER = TemplateDef(
    "debt_reminder",
    "Assalomu alaykum, {{1}}! {{2}} do'konidagi qarzingiz bo'yicha eslatma: umumiy qarz "
    "{{3}} so'm, to'lov muddati: {{4}}. Imkoniyatingiz bo'lganda to'lovni amalga oshirishingizni "
    "so'raymiz. Rahmat!",
    ("Aziz", "Baraka", "120 000", "20.10.2026"),
)
DEBT_OVERDUE = TemplateDef(
    "debt_overdue",
    "Assalomu alaykum, {{1}}! {{2}} do'konidagi {{3}} so'm qarzingizning to'lov muddati "
    "({{4}}) o'tdi. Imkoniyatingiz bo'lganda to'lovni amalga oshirishingizni iltimos qilamiz. "
    "Savollar bo'lsa, do'kon bilan bog'laning. Rahmat!",
    ("Aziz", "Baraka", "120 000", "20.10.2026"),
)
PAYMENT_RECEIVED = TemplateDef(
    "payment_received",
    "Assalomu alaykum, {{1}}! {{2}} do'koni {{3}} so'm to'lovingizni qabul qildi. "
    "Qolgan qarz: {{4}} so'm. Rahmat!",
    ("Aziz", "Baraka", "50 000", "70 000"),
)
# The final payment gets this message *instead of* payment_received (never
# both): it confirms the amount paid and that nothing is left (FT-4), in one
# billable template rather than two for the same event.
DEBT_CLOSED = TemplateDef(
    "debt_closed",
    "Assalomu alaykum, {{1}}! {{2}} do'koni {{3}} so'm to'lovingizni qabul qildi. "
    "Qolgan qarz: 0 so'm. Qarzingiz to'liq yopildi. Rahmat!",
    ("Aziz", "Baraka", "70 000"),
)

ALL_TEMPLATES = (DEBT_ADDED, DEBT_REMINDER, DEBT_OVERDUE, PAYMENT_RECEIVED, DEBT_CLOSED)


def money(amount: int) -> str:
    """120000 -> "120 000" (same grouping as the app's formatMoney)."""
    return f"{int(amount):,}".replace(",", " ")


def day(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else NO_DUE_DATE


def param(value: str, limit: int = 60) -> str:
    """Template parameters may not contain newlines, tabs or runs of spaces."""
    return re.sub(r"\s+", " ", str(value)).strip()[:limit] or "-"


# --------------------------------------------------------------------------
# Free-text bot replies (only ever sent inside the customer-service window)
# --------------------------------------------------------------------------

HELP_MENU = (
    "Assalomu alaykum! Men do'konlardagi qarzingiz haqida ma'lumot beraman.\n\n"
    "• *qarz* yoki *qoldiq* — joriy qarz va so'nggi 5 ta amal\n"
    "• *STOP* yoki *to'xtat* — xabarlarni to'xtatish\n"
    "• *START* — xabarlarni qayta yoqish"
)
NOT_REGISTERED = (
    "Kechirasiz, bu raqam hech qaysi do'konda WhatsApp xabarlari uchun ro'yxatdan "
    "o'tmagan. Ma'lumot uchun do'kon bilan bog'laning."
)
UNSUBSCRIBED = (
    "Siz do'kon xabarlaridan muvaffaqiyatli obunadan chiqdingiz. Endi sizga qarz haqida "
    "xabar yuborilmaydi. Qayta yoqish uchun START deb yozing."
)
RESUBSCRIBED = "Xabarlar qayta yoqildi. Rahmat! To'xtatish uchun istalgan vaqtda STOP deb yozing."
ALREADY_SUBSCRIBED = "Xabarlar allaqachon yoqilgan. To'xtatish uchun STOP deb yozing."
CANNOT_RESUBSCRIBE = (
    "Xabarlarni yoqib bo'lmadi: bu raqam uchun avval berilgan rozilik topilmadi. "
    "Iltimos, do'konga murojaat qiling."
)
CHOOSE_SHOP = (
    "Raqamingiz bir nechta do'konda ro'yxatdan o'tgan. Qaysi do'kon bo'yicha ma'lumot kerak?"
)
CHOOSE_SHOP_TEXT_HINT = "Do'kon raqamini yozib yuboring (masalan: 1)."
CHOOSE_SHOP_BUTTON = "Do'konni tanlash"
INVALID_CHOICE = "Bunday tanlov yo'q. Iltimos, ro'yxatdagi raqamlardan birini yozing."


def balance_reply(shop_name: str, balance: int, operations: list[tuple]) -> str:
    """operations: (created_at, entry_type, amount) — newest first, at most 5."""
    lines = [f"*{shop_name}* do'koni"]
    if balance > 0:
        lines.append(f"Joriy qarzingiz: *{money(balance)} so'm*")
    elif balance < 0:
        lines.append(f"Qarzingiz yo'q. Do'kondagi haqingiz: {money(-balance)} so'm")
    else:
        lines.append("Qarzingiz yo'q. Rahmat!")
    if operations:
        lines.append("")
        lines.append("So'nggi amallar:")
        for created_at, entry_type, amount in operations:
            label = "Qarz" if entry_type == "debt" else "To'lov"
            sign = "+" if amount > 0 else "−"
            lines.append(f"{created_at:%d.%m.%Y} — {label} {sign}{money(abs(amount))} so'm")
    lines.append("")
    lines.append(UNSUBSCRIBE_FOOTER)
    return "\n".join(lines)


def shop_menu_text(shop_names: list[str]) -> str:
    rows = "\n".join(f"{i}. {name}" for i, name in enumerate(shop_names, start=1))
    return f"{CHOOSE_SHOP}\n\n{rows}\n\n{CHOOSE_SHOP_TEXT_HINT}"
