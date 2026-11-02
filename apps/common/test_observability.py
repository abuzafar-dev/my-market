"""Sentry is optional: without a DSN nothing is initialised and nothing leaves
the server; with one, personal data (phones, customer names) stays out."""

from unittest.mock import patch

from django.test import SimpleTestCase

from config.observability import init_sentry, parse_sample_rate, scrub_event


class InitSentryTests(SimpleTestCase):
    @patch("sentry_sdk.init")
    def test_empty_dsn_does_not_init(self, init):
        self.assertFalse(init_sentry("", environment="test"))
        self.assertFalse(init_sentry("   ", environment="test"))
        init.assert_not_called()

    @patch("sentry_sdk.init")
    def test_dsn_inits_without_pii(self, init):
        self.assertTrue(init_sentry("https://k@o.ingest.sentry.io/1", environment="production"))

        kwargs = init.call_args.kwargs
        self.assertEqual(kwargs["dsn"], "https://k@o.ingest.sentry.io/1")
        self.assertFalse(kwargs["send_default_pii"])
        # send_default_pii does not cover these: request bodies (customer
        # phone + name in a POST) and stack-frame locals would still be sent.
        self.assertEqual(kwargs["max_request_body_size"], "never")
        self.assertFalse(kwargs["include_local_variables"])
        self.assertIs(kwargs["before_send"], scrub_event)
        self.assertEqual(kwargs["environment"], "production")
        self.assertEqual(kwargs["traces_sample_rate"], 0.0)
        self.assertEqual(
            {type(i).__name__ for i in kwargs["integrations"]},
            {"DjangoIntegration", "CeleryIntegration"},
        )

    @patch("sentry_sdk.init")
    def test_traces_sample_rate_is_passed_through(self, init):
        init_sentry("https://k@o.ingest.sentry.io/1", environment="staging", traces_sample_rate=0.2)

        self.assertEqual(init.call_args.kwargs["traces_sample_rate"], 0.2)


class ScrubEventTests(SimpleTestCase):
    def test_query_string_and_cookies_are_dropped(self):
        # ?search=+998901112233 on the customer list is a phone number.
        event = {
            "request": {
                "url": "https://x.uz/api/customers/",
                "query_string": "search=%2B998901112233",
                "cookies": {"refresh": "secret"},
                "data": {"phone": "+998901112233"},
                "method": "GET",
            },
            "message": "boom",
        }

        scrubbed = scrub_event(event, {})

        self.assertEqual(
            scrubbed["request"], {"url": "https://x.uz/api/customers/", "method": "GET"}
        )
        self.assertEqual(scrubbed["message"], "boom")

    def test_event_without_request_passes_through(self):
        self.assertEqual(scrub_event({"message": "celery"}, {}), {"message": "celery"})


class ParseSampleRateTests(SimpleTestCase):
    def test_blank_means_zero_instead_of_crashing_start_up(self):
        self.assertEqual(parse_sample_rate(""), 0.0)
        self.assertEqual(parse_sample_rate("  "), 0.0)

    def test_number_is_parsed(self):
        self.assertEqual(parse_sample_rate("0.25"), 0.25)
