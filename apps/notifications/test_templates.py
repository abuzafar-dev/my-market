"""Template contract: what is submitted to Meta (templates.py, printed by
`whatsapp_templates`) and what deliver() sends must agree, variable for
variable. This checks local format and parameter counts only — it says
nothing about whether Meta has approved anything."""

import io
import json
import re
from datetime import date

from django.core.management import call_command
from django.test import SimpleTestCase

from . import templates as tpl
from .testing import NotificationTestCase

PLACEHOLDER = re.compile(r"{{(\d+)}}")
# Variables each template carries, by meaning (docs/WHATSAPP.md §6).
EXPECTED_VARIABLES = {
    "debt_added": ["name", "shop", "added", "total", "due"],
    "debt_reminder": ["name", "shop", "total", "due"],
    "debt_overdue": ["name", "shop", "overdue", "due"],
    "payment_received": ["name", "shop", "paid", "remaining"],
    # The closure replaces payment_received for the payment that clears the
    # debt, so it still has to say how much was paid (FT-4).
    "debt_closed": ["name", "shop", "paid"],
}


class TemplateDefinitionTests(SimpleTestCase):
    def test_the_five_templates_of_the_tz_exist_once(self):
        self.assertEqual(sorted(t.name for t in tpl.ALL_TEMPLATES), sorted(EXPECTED_VARIABLES))

    def test_placeholders_are_sequential_and_match_the_examples(self):
        for t in tpl.ALL_TEMPLATES:
            numbers = [int(n) for n in PLACEHOLDER.findall(t.body)]
            expected = len(EXPECTED_VARIABLES[t.name])
            self.assertEqual(numbers, list(range(1, expected + 1)), t.name)
            self.assertEqual(len(t.example), expected, t.name)

    def test_local_meta_format_rules(self):
        """Rules WhatsApp Manager applies to Utility templates that can be
        checked locally (approval itself cannot)."""
        for t in tpl.ALL_TEMPLATES:
            body = t.body
            self.assertRegex(t.name, r"^[a-z0-9_]{1,512}$")
            self.assertFalse(body.lstrip().startswith("{{"), f"{t.name}: starts with a variable")
            self.assertFalse(body.rstrip(" .!").endswith("}}"), f"{t.name}: ends with a variable")
            self.assertNotRegex(body, r"}}\s*{{", f"{t.name}: adjacent variables")
            self.assertLessEqual(len(body), 1024, t.name)
            self.assertNotIn("\n\n\n", body)
            for value in t.example:
                self.assertEqual(tpl.param(value), value, f"{t.name}: example not a valid param")
        self.assertLessEqual(len(tpl.UNSUBSCRIBE_FOOTER), 60)
        self.assertLessEqual(len(tpl.BALANCE_BUTTON), 25)

    def test_every_template_has_the_stop_footer_and_the_balance_button(self):
        out = io.StringIO()
        call_command("whatsapp_templates", stdout=out)
        definitions = json.loads(out.getvalue())
        self.assertEqual(len(definitions), 5)
        for definition in definitions:
            self.assertEqual(definition["category"], "UTILITY")
            components = {c["type"]: c for c in definition["components"]}
            self.assertEqual(components["FOOTER"]["text"], tpl.UNSUBSCRIBE_FOOTER)
            self.assertEqual(
                components["BUTTONS"]["buttons"],
                [{"type": "QUICK_REPLY", "text": tpl.BALANCE_BUTTON}],
            )
            n = len(PLACEHOLDER.findall(components["BODY"]["text"]))
            self.assertEqual(len(components["BODY"]["example"]["body_text"][0]), n)

    def test_param_strips_what_meta_refuses_in_a_variable(self):
        self.assertEqual(tpl.param("Aziz\n\tAka   "), "Aziz Aka")
        self.assertEqual(tpl.param("   "), "-")
        self.assertEqual(len(tpl.param("x" * 200)), 60)


class TemplatePayloadTests(NotificationTestCase):
    """What deliver() actually sends for every kind, against the definitions."""

    def sent(self):
        by_name = {t.name: t for t in tpl.ALL_TEMPLATES}
        out = {}
        for _, message in self.channel.sent:
            if message["type"] != "template":
                continue
            template = message["template"]
            body = next(c for c in template["components"] if c["type"] == "body")
            params = [p["text"] for p in body["parameters"]]
            definition = by_name[template["name"]]
            self.assertEqual(
                len(params), len(PLACEHOLDER.findall(definition.body)), template["name"]
            )
            self.assertTrue(all(p and "\n" not in p for p in params), params)
            out.setdefault(template["name"], params)
        return out

    def test_every_kind_sends_exactly_the_defined_variables(self):
        from . import services

        self.at(2026, 10, 10, 12, 0)
        self.add_debt(100_000, due_date=date(2026, 10, 12))
        self.advance(minutes=11)
        self.flush()  # debt_added
        self.add_payment(30_000)
        self.flush()  # payment_received
        self.at(2026, 10, 11, 12, 0)
        with self.captureOnCommitCallbacks(execute=True):
            services.schedule_reminders()
        self.flush()  # debt_reminder
        self.at(2026, 10, 13, 12, 0)
        with self.captureOnCommitCallbacks(execute=True):
            services.schedule_reminders()
        self.flush()  # debt_overdue
        self.add_payment(70_000)
        self.flush()  # debt_closed

        sent = self.sent()
        self.assertEqual(
            sent,
            {
                "debt_added": ["Aziz", "Baraka", "100 000", "100 000", "12.10.2026"],
                "payment_received": ["Aziz", "Baraka", "30 000", "70 000"],
                "debt_reminder": ["Aziz", "Baraka", "70 000", "12.10.2026"],
                "debt_overdue": ["Aziz", "Baraka", "70 000", "12.10.2026"],
                "debt_closed": ["Aziz", "Baraka", "70 000"],
            },
        )
