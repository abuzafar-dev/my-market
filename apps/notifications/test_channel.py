"""The WhatsApp adapter on its own: HTTP request shape, error classification,
signatures, phone handling. http.client is mocked — no network."""

import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from .channels import ChannelError
from .channels.whatsapp import WhatsAppCloudChannel
from .phone import mask, to_e164


def channel(**kwargs):
    defaults = {
        "access_token": "SECRET-TOKEN",
        "phone_number_id": "123",
        "api_version": "v0.test",
        "app_secret": "s3cret",  # pragma: allowlist secret
        "api_base": "https://graph.example",
    }
    return WhatsAppCloudChannel(**{**defaults, **kwargs})


class FakeHTTP:
    """Replaces http.client.HTTPSConnection. ``fail_at`` picks the stage that
    raises ``error``: "connect" (nothing sent yet), "request" (while writing),
    "response" (waiting for the answer) or "read" (reading the body)."""

    def __init__(self, status=200, body=None, fail_at=None, error=None):
        self.status = status
        self.body = (
            json.dumps({"messages": [{"id": "wamid.ABC"}]}).encode() if body is None else body
        )
        self.fail_at = fail_at
        self.error = error or TimeoutError()
        self.requests = []
        self.connected = self.closed = False

    def __call__(self, host, port=None, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        return self

    def _maybe_fail(self, stage):
        if self.fail_at == stage:
            raise self.error

    def connect(self):
        self._maybe_fail("connect")
        self.connected = True

    def request(self, method, path, body=None, headers=None):
        self._maybe_fail("request")
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        self._maybe_fail("response")
        fake = self

        class Response:
            status = fake.status

            def read(self):
                fake._maybe_fail("read")
                return fake.body

        return Response()

    def close(self):
        self.closed = True

    def patch(self):
        return patch("http.client.HTTPSConnection", self)


def send(fake, **kwargs):
    with fake.patch():
        return channel(**kwargs).send_text("+998901234567", "x")


class SendTests(SimpleTestCase):
    def test_template_request(self):
        fake = FakeHTTP()
        with fake.patch():
            result = channel().send_template(
                "+998901234567", "debt_added", "uz", ["Aziz", "Baraka"], quick_reply="BALANCE"
            )
        self.assertEqual(result.external_id, "wamid.ABC")
        self.assertEqual((fake.host, fake.timeout), ("graph.example", 15))
        method, path, raw, headers = fake.requests[0]
        self.assertEqual((method, path), ("POST", "/v0.test/123/messages"))
        self.assertEqual(headers["Authorization"], "Bearer SECRET-TOKEN")
        body = json.loads(raw)
        self.assertEqual(body["to"], "998901234567")
        self.assertEqual(body["template"]["name"], "debt_added")
        self.assertEqual(
            body["template"]["components"][0]["parameters"],
            [{"type": "text", "text": "Aziz"}, {"type": "text", "text": "Baraka"}],
        )
        self.assertEqual(body["template"]["components"][1]["sub_type"], "quick_reply")
        self.assertTrue(fake.closed)

    def test_unconfigured_never_calls_out(self):
        fake = FakeHTTP()
        with self.assertRaises(ChannelError) as ctx:
            send(fake, api_version="")
        self.assertFalse(fake.connected)
        self.assertFalse(ctx.exception.retryable)
        self.assertFalse(channel(access_token="").is_configured())

    def test_errors_meta_answered_are_classified_by_code_then_status(self):
        cases = [
            (500, {"error": {"code": 131000}}, True),
            (503, {}, True),
            (429, {"error": {"code": 130429}}, True),
            (400, {"error": {"code": 131026, "message": "Undeliverable"}}, False),
            (400, {"error": {"code": 132001}}, False),
            (401, {"error": {"code": 190}}, False),
            (400, {"error": {"code": 131016}}, True),  # code wins over status
            (400, {"error": {"code": 99999}}, False),
            (502, b"<html>bad gateway</html>", True),  # not JSON: status decides
        ]
        for status, body, retryable in cases:
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            with self.assertRaises(ChannelError) as ctx:
                send(FakeHTTP(status=status, body=raw))
            self.assertEqual(ctx.exception.retryable, retryable, (status, body))
            self.assertNotEqual(ctx.exception.code, "send_unknown")

    def test_failure_before_anything_was_sent_is_retryable(self):
        import socket
        import ssl

        for error in [
            socket.gaierror("no such host"),
            ConnectionRefusedError(),
            TimeoutError("connect timed out"),
            ssl.SSLError("handshake"),
        ]:
            fake = FakeHTTP(fail_at="connect", error=error)
            with self.assertRaises(ChannelError) as ctx:
                send(fake)
            self.assertEqual((ctx.exception.code, ctx.exception.retryable), ("network", True))
            self.assertEqual(fake.requests, [])
            self.assertNotIn("SECRET-TOKEN", str(ctx.exception) + ctx.exception.detail)

    def test_outcome_unknown_once_the_request_started_is_never_retryable(self):
        import http.client

        cases = [
            ("request", BrokenPipeError()),  # died while writing
            ("response", TimeoutError()),  # read timeout waiting for Meta
            ("response", http.client.RemoteDisconnected("closed")),
            ("response", ConnectionResetError()),
            ("read", TimeoutError()),  # 200 whose body never arrived
            ("read", http.client.IncompleteRead(b"")),
        ]
        for stage, error in cases:
            with self.assertRaises(ChannelError) as ctx:
                send(FakeHTTP(fail_at=stage, error=error))
            self.assertEqual(
                (ctx.exception.code, ctx.exception.retryable),
                ("send_unknown", False),
                (stage, error),
            )

        for body in [b"<html>", b"{}", json.dumps({"messages": [{"id": ""}]}).encode()]:
            with self.assertRaises(ChannelError) as ctx:
                send(FakeHTTP(status=200, body=body))
            self.assertEqual((ctx.exception.code, ctx.exception.retryable), ("send_unknown", False))

    def test_plain_http_base_uses_http_connection(self):
        fake = FakeHTTP()
        with patch("http.client.HTTPConnection", fake):
            channel(api_base="http://127.0.0.1:8099").send_text("+998901234567", "x")
        self.assertEqual((fake.host, fake.port), ("127.0.0.1", 8099))

    def test_logs_mask_the_number_and_hide_token_and_body(self):
        with (
            FakeHTTP().patch(),
            self.assertLogs("apps.notifications", level="INFO") as logs,
        ):
            import logging

            logging.disable(logging.NOTSET)
            try:
                channel().send_text("+998901234567", "Qarzingiz 50 000 so'm")
            finally:
                logging.disable(logging.CRITICAL)
        output = "\n".join(logs.output)
        self.assertNotIn("901234567", output)
        self.assertNotIn("SECRET-TOKEN", output)
        self.assertNotIn("50 000", output)
        self.assertIn("+99890", output)


class SignatureTests(SimpleTestCase):
    def test_verify(self):
        body = b'{"a":1}'
        good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        self.assertTrue(channel().verify_signature(body, good))
        self.assertFalse(channel().verify_signature(body + b" ", good))
        self.assertFalse(channel().verify_signature(body, good.upper()))
        self.assertFalse(channel().verify_signature(body, None))
        self.assertFalse(channel(app_secret="").verify_signature(body, good))


class PhoneTests(SimpleTestCase):
    def test_to_e164(self):
        for raw in ["+998 90 123-45-67", "998901234567", "901234567", "(90) 123 45 67"]:
            self.assertEqual(to_e164(raw), "+998901234567", raw)
        for raw in ["", None, "12345", "+79123456789", "+998 01 234 56 78", "9989012345678"]:
            self.assertIsNone(to_e164(raw), raw)

    def test_mask(self):
        self.assertEqual(mask("+998901234567"), "+99890*****67")
        self.assertEqual(mask(""), "-")


class DeploymentCheckTests(SimpleTestCase):
    def test_per_process_cache_with_whatsapp_configured_is_flagged(self):
        from django.test import override_settings

        from .checks import shared_cache_for_whatsapp

        locmem = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        redis = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache"}}
        on = {"WHATSAPP_ACCESS_TOKEN": "t", "WHATSAPP_PHONE_NUMBER_ID": "1"}
        with override_settings(CACHES=locmem, **on):
            self.assertEqual(
                [w.id for w in shared_cache_for_whatsapp(None)], ["notifications.W001"]
            )
        with override_settings(CACHES=redis, **on):
            self.assertEqual(shared_cache_for_whatsapp(None), [])
        with override_settings(CACHES=locmem, WHATSAPP_ACCESS_TOKEN=""):
            self.assertEqual(shared_cache_for_whatsapp(None), [])
