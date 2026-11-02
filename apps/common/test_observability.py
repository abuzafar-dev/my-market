"""Sentry is optional: without a DSN nothing is initialised and nothing leaves
the server; with one, personal data (phones, customer names) stays out."""

from unittest.mock import patch

from django.test import SimpleTestCase

from config.observability import init_sentry


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
