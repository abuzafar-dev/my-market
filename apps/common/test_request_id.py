"""Every request gets an ID: echoed in X-Request-ID and stamped on each log
line written while it is handled, so a user's "it failed at 14:05" can be
matched to the server log."""

import logging
import re

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from apps.common.logging import RequestIdFilter, request_id_var
from apps.common.middleware import RequestIdMiddleware

HEX32 = re.compile(r"[0-9a-f]{32}")


class RequestIdHeaderTests(TestCase):
    def test_response_has_generated_id(self):
        response = self.client.get("/healthz/")

        self.assertRegex(response["X-Request-ID"], HEX32)

    def test_each_request_gets_its_own_id(self):
        first = self.client.get("/healthz/")["X-Request-ID"]
        second = self.client.get("/healthz/")["X-Request-ID"]

        self.assertNotEqual(first, second)

    def test_valid_incoming_id_is_kept(self):
        response = self.client.get("/healthz/", HTTP_X_REQUEST_ID="abc-12345678")

        self.assertEqual(response["X-Request-ID"], "abc-12345678")

    def test_bad_incoming_id_is_replaced(self):
        for bad in ("x" * 200, "abc\nINFO fake line", "short", "a b c d e f g h", ""):
            with self.subTest(bad=bad):
                response = self.client.get("/healthz/", HTTP_X_REQUEST_ID=bad)

                self.assertNotEqual(response["X-Request-ID"], bad)
                self.assertRegex(response["X-Request-ID"], HEX32)

    @override_settings(CORS_ALLOWED_ORIGINS=["http://localhost:5173"])
    def test_header_is_readable_by_the_spa(self):
        response = self.client.get("/healthz/", HTTP_ORIGIN="http://localhost:5173")

        self.assertIn("x-request-id", response["Access-Control-Expose-Headers"].lower())


class RequestIdLoggingTests(SimpleTestCase):
    def _record(self):
        record = logging.LogRecord("apps.test", logging.WARNING, __file__, 1, "x", None, None)
        RequestIdFilter().filter(record)
        return record

    def test_outside_a_request_the_id_is_a_dash(self):
        self.assertEqual(self._record().request_id, "-")

    def test_log_inside_a_request_carries_its_id(self):
        seen = {}

        def view(request):
            seen["record"] = self._record()
            seen["request_attr"] = request.request_id
            return HttpResponse("ok")

        response = RequestIdMiddleware(view)(RequestFactory().get("/"))

        self.assertEqual(seen["record"].request_id, response["X-Request-ID"])
        self.assertEqual(seen["request_attr"], response["X-Request-ID"])

    def test_id_is_cleared_after_the_request(self):
        RequestIdMiddleware(lambda request: HttpResponse("ok"))(RequestFactory().get("/"))

        self.assertEqual(request_id_var.get(), "-")
