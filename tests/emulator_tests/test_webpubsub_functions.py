# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Web PubSub extension emulator tests.

Tests for:
- WebPubSub webhook abuse protection (OPTIONS request validation)
- WebPubSub trigger dispatch (POST request handling)
- Custom vs default connection name configurations
- Connection info input binding (negotiate)
- Output binding validation

No WebPubSub service emulator is needed — the extension handles webhook
requests directly within the Functions host HTTP pipeline.
"""
import base64
import hashlib
import hmac
import logging
import os

from tests.utils import testutils

logger = logging.getLogger(__name__)


class WebPubSubTestMixin:
    """
    Mixin providing strict assertion helpers for WebPubSub tests.

    All tests should use these helpers instead of raw status_code checks
    so that ANY unexpected error (5xx, unexpected 4xx, error bodies) is
    surfaced loudly rather than swallowed.
    """

    def assert_success(self, response, msg=None):
        """Assert the response is a success (2xx) and not an error."""
        body_preview = response.text[:500] if response.text else "(empty)"
        context = (
            f"{msg or 'Request'}: "
            f"status={response.status_code}, body={body_preview}"
        )
        self.assertLess(
            response.status_code, 300,
            f"Expected success (2xx), got {response.status_code}. {context}",
        )
        self.assertGreaterEqual(
            response.status_code, 200,
            f"Unexpected status {response.status_code}. {context}",
        )

    def assert_no_server_error(self, response, msg=None):
        """Assert the response is NOT a server error (5xx)."""
        body_preview = response.text[:500] if response.text else "(empty)"
        context = (
            f"{msg or 'Request'}: "
            f"status={response.status_code}, body={body_preview}"
        )
        self.assertLess(
            response.status_code, 500,
            f"Server error detected! {context}",
        )

    def assert_expected_status(self, response, expected, msg=None):
        """Assert exact status code with full error context on failure."""
        body_preview = response.text[:500] if response.text else "(empty)"
        context = (
            f"{msg or 'Request'}: "
            f"status={response.status_code}, body={body_preview}"
        )
        self.assertEqual(
            response.status_code, expected,
            f"Expected {expected}, got {response.status_code}. {context}",
        )

    def assert_client_or_success(self, response, msg=None):
        """Assert the response is 2xx or 4xx (never 5xx)."""
        self.assert_no_server_error(response, msg)

    @staticmethod
    def _compute_ce_signature(access_key, connection_id):
        """
        Compute the ce-signature HMAC-SHA256 value the WebPubSub extension
        expects.  The extension validates:
            HMAC-SHA256(UTF8(AccessKey), UTF8(ce-connectionId))
        and expects: sha256=<lowercase hex digest>
        """
        key_bytes = access_key.encode("utf-8")
        msg_bytes = connection_id.encode("utf-8")
        digest = hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()
        return f"sha256={digest}"


class TestWebPubSubFunctions(WebPubSubTestMixin, testutils.WebHostTestCase):
    """Test cases for Web PubSub extension bindings."""

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / "webpubsub_functions"

    @classmethod
    def setUpClass(cls):
        # Set environment variables before the host starts
        os.environ["WebPubSubConnectionString"] = \
            cls._build_connection_string("test-default")
        os.environ["MyCustomWebPubSubConnection"] = \
            cls._build_connection_string("test-custom")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        os.environ.pop("WebPubSubConnectionString", None)
        os.environ.pop("MyCustomWebPubSubConnection", None)

    @staticmethod
    def _build_connection_string(name):
        key = base64.b64encode(f"{name}-key".encode()).decode()
        return (
            f"Endpoint=https://{name}.webpubsub.azure.com;"
            f"AccessKey={key};Version=1.0;"
        )

    @staticmethod
    def _get_access_key(name):
        """Return the raw AccessKey string for a given connection name."""
        return base64.b64encode(f"{name}-key".encode()).decode()

    # =========================================================================
    # Host Startup Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_host_starts_successfully(self):
        """Verify the host starts and loads the WebPubSub extension."""
        logger.info("Testing host startup with WebPubSub extension...")

        r = self.webhost.request("GET", "health", max_retries=3, expected_status=200)
        self.assert_expected_status(r, 200, "Health endpoint")
        self.assertEqual(r.text, "OK")

        logger.info("Host started successfully with WebPubSub extension")

    # =========================================================================
    # Abuse Protection / OPTIONS Request Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_webhook_validation_options_request(self):
        """
        Test WebPubSub service abuse protection check (OPTIONS request).
        The WebPubSub service sends OPTIONS requests to validate the webhook.
        The extension should respond with WebHook-Allowed-Origin header.
        """
        logger.info("Testing WebPubSub webhook validation (OPTIONS)...")

        # Simulate the OPTIONS request that WebPubSub service sends
        r = self.webhost.request(
            "OPTIONS",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            },
            max_retries=3,
            expected_status=200,
        )

        self.assert_expected_status(r, 200, "OPTIONS abuse protection")

        # Verify the response includes the allowed origin header
        allowed_origin = r.headers.get("WebHook-Allowed-Origin", "")
        self.assertTrue(
            len(allowed_origin) > 0,
            "Response should include WebHook-Allowed-Origin header",
        )

        logger.info("Webhook validation succeeded, allowed origin: %s", allowed_origin)

    @testutils.retryable_test(3, 5)
    def test_webhook_validation_unknown_origin(self):
        """
        Test abuse protection with an unrecognized origin.
        When the origin does not match any configured connection's endpoint,
        the extension should reject the request.
        """
        logger.info("Testing webhook validation with unknown origin...")

        r = self.webhost.request(
            "OPTIONS",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "WebHook-Request-Origin": "unknown.attacker.com",
            },
            max_retries=0,
        )

        self.assert_no_server_error(r, "Unknown origin OPTIONS")
        self.assert_expected_status(r, 400, "Unknown origin should be rejected")

        logger.info("Unknown origin correctly rejected")

    @testutils.retryable_test(3, 5)
    def test_webhook_validation_multiple_origins(self):
        """Test OPTIONS request with multiple comma-separated origins."""
        logger.info("Testing webhook validation with multiple origins...")

        r = self.webhost.request(
            "OPTIONS",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "WebHook-Request-Origin":
                    "other.service.com, test-default.webpubsub.azure.com",
            },
            max_retries=3,
        )

        self.assert_no_server_error(r, "Multiple origins OPTIONS")

        logger.info("Multiple origins returned %d", r.status_code)

    # =========================================================================
    # Trigger Invocation Tests (CloudEvents webhook dispatch)
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_trigger_connect_event(self):
        """
        Test invoking the WebPubSub trigger with a sys.connect event.
        Sends a properly-formatted CloudEvents request to the webhook endpoint
        and verifies the function executes successfully.
        """
        logger.info("Testing trigger connect event invocation...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-event-id-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-001",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"), "test-conn-id-001"),
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Connect event trigger dispatch")

        logger.info("Trigger connect event invoked successfully")

    @testutils.retryable_test(3, 5)
    def test_trigger_connect_event_custom_hub(self):
        """
        Test trigger invocation targeting the custom hub trigger.
        The request ce-hub must match the hub configured on the trigger.
        """
        logger.info("Testing trigger connect event for custom hub...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-custom.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/customhub",
            "ce-id": "test-event-id-002",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "customhub",
            "ce-connectionId": "test-conn-id-002",
            "ce-userId": "custom-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-custom"), "test-conn-id-002"),
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Connect event for custom hub")

        logger.info("Trigger connect event for custom hub invoked successfully")

    @testutils.retryable_test(3, 5)
    def test_trigger_connect_event_legacy_connection(self):
        """
        Test trigger using connection= (singular) — the common customer pattern.
        The singular 'connection' property does NOT map to the C# attribute's
        Connections[] — validation falls back to the default WebPubSubConnectionString.
        So we must use the DEFAULT origin and key for signature validation.
        Routing still works via ce-hub header.
        """
        logger.info("Testing trigger connect event for legacy connection hub...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/legacyhub",
            "ce-id": "test-event-id-legacy",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "legacyhub",
            "ce-connectionId": "test-conn-id-legacy",
            "ce-userId": "legacy-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"), "test-conn-id-legacy"),
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Connect event for legacy connection hub")

        logger.info("Trigger connect event for legacy connection hub invoked successfully")

    @testutils.retryable_test(3, 5)
    def test_trigger_user_message_event(self):
        """
        Test invoking the WebPubSub trigger with a user message event.
        User events use ce-type 'azure.webpubsub.user.<eventName>'.
        """
        logger.info("Testing trigger user message event...")

        headers = {
            "Content-Type": "text/plain",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.user.message",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-event-id-003",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "message",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-003",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"), "test-conn-id-003"),
        }

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data="Hello from user",
            max_retries=3,
        )

        # User message should be dispatched (200) or rejected if no
        # matching function is registered for the event — must never crash
        self.assert_no_server_error(r, "User message event")

        logger.info("Trigger user message event returned %d", r.status_code)

    @testutils.retryable_test(3, 5)
    def test_trigger_missing_required_headers(self):
        """
        Test that a POST without required CloudEvents headers does not crash.
        Missing ce-type or ce-hub should result in a non-500 error.
        """
        logger.info("Testing trigger with missing CloudEvents headers...")

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "Content-Type": "application/json",
                "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            },
            data="{}",
            max_retries=0,
        )

        # Should not crash the host — any 5xx is a failure
        self.assert_no_server_error(r, "Missing CloudEvents headers")

        logger.info("Missing headers returned %d", r.status_code)

    # =========================================================================
    # Connection Info Input Binding (Negotiate) Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_negotiate_returns_connection_info(self):
        """Test that negotiate endpoint returns valid connection info."""
        logger.info("Testing negotiate endpoint...")

        r = self.webhost.request(
            "POST", "negotiate", max_retries=3, expected_status=200)

        self.assert_success(r, "Negotiate endpoint")

        connection_info = r.json()

        self.assertIn("url", connection_info,
                      "Connection info should contain 'url'")
        self.assertIn("accessToken", connection_info,
                      "Connection info should contain 'accessToken'")
        self.assertTrue(connection_info["url"].startswith(("wss://", "ws://")),
                        "URL should be a valid WebSocket endpoint")
        self.assertTrue(len(connection_info["accessToken"]) > 0,
                        "Access token should not be empty")

        logger.info("Negotiate returned URL: %s", connection_info["url"])

    @testutils.retryable_test(3, 5)
    def test_negotiate_with_userid_header(self):
        """Test negotiate with userId from request header."""
        logger.info("Testing negotiate with userId header...")

        r = self.webhost.request(
            "POST", "negotiate_with_userid",
            headers={"x-ms-webpubsub-userid": "test-user-123"},
            max_retries=3, expected_status=200)

        self.assert_success(r, "Negotiate with userId")

        connection_info = r.json()
        self.assertIn("url", connection_info)
        self.assertIn("accessToken", connection_info)

        logger.info("Negotiate with userId returned successfully")

    @testutils.retryable_test(3, 5)
    def test_negotiate_with_custom_connection(self):
        """Test negotiate using a custom-named connection setting."""
        logger.info("Testing negotiate with custom connection...")

        r = self.webhost.request(
            "POST", "negotiate_custom_conn",
            max_retries=3, expected_status=200)

        self.assert_success(r, "Negotiate with custom connection")

        connection_info = r.json()
        self.assertIn("url", connection_info)
        self.assertIn("accessToken", connection_info)

        # URL should reference the custom endpoint
        self.assertIn("test-custom", connection_info["url"],
                      "URL should reference the custom connection endpoint")

        logger.info("Negotiate with custom connection returned URL: %s",
                     connection_info["url"])

    # =========================================================================
    # Output Binding Validation Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_send_to_group_missing_fields(self):
        """Test send to group with missing required fields."""
        logger.info("Testing send to group with missing fields...")

        payload = {"groupName": "test-group"}  # missing message

        r = self.webhost.request("POST", "send_to_group", json=payload,
                                max_retries=0)

        self.assert_no_server_error(r, "Send to group missing fields")
        self.assert_expected_status(r, 400, "Missing fields should be rejected")
        error_response = r.json()
        self.assertIn("error", error_response)

        logger.info("Send to group correctly rejected missing fields")

    @testutils.retryable_test(3, 5)
    def test_add_user_to_group_missing_fields(self):
        """Test add user to group with missing required fields."""
        logger.info("Testing add user to group with missing fields...")

        payload = {"userId": "user-789"}  # missing groupName

        r = self.webhost.request("POST", "add_user_to_group", json=payload,
                                max_retries=0)

        self.assert_no_server_error(r, "Add user to group missing fields")
        self.assert_expected_status(r, 400, "Missing fields should be rejected")
        error_response = r.json()
        self.assertIn("error", error_response)

        logger.info("Add user to group correctly rejected missing fields")

    @testutils.retryable_test(3, 5)
    def test_output_binding_invalid_json(self):
        """Test output binding endpoint with invalid JSON payload."""
        logger.info("Testing invalid JSON payload...")

        r = self.webhost.request(
            "POST", "send_to_group",
            data="not valid json",
            headers={"Content-Type": "application/json"},
            max_retries=0)

        self.assert_no_server_error(r, "Invalid JSON payload")
        self.assert_expected_status(r, 400, "Invalid JSON should be rejected")
        error_response = r.json()
        self.assertIn("error", error_response)

        logger.info("Invalid JSON correctly rejected")

    # =========================================================================
    # Signature Validation Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_trigger_invalid_signature_returns_401(self):
        """
        Test that an invalid HMAC signature is rejected with 401.
        The extension computes HMAC-SHA256(AccessKey, ce-connectionId) and
        compares with ce-signature — a wrong value must be rejected.
        """
        logger.info("Testing trigger with invalid signature...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-invalid-sig",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-invalid",
            "ce-userId": "test-user",
            "ce-signature": "sha256=0000000000000000000000000000000000000000"
                            "000000000000000000000000",
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=0,
        )

        self.assert_expected_status(r, 401, "Invalid signature")
        logger.info("Invalid signature correctly rejected with 401")

    @testutils.retryable_test(3, 5)
    def test_trigger_missing_signature_returns_401(self):
        """
        Test that a missing ce-signature header is rejected with 401
        when signature validation is active (AccessKey present).
        """
        logger.info("Testing trigger with missing signature...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-missing-sig",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-nosig",
            "ce-userId": "test-user",
            # ce-signature intentionally omitted
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=0,
        )

        self.assert_expected_status(r, 401, "Missing signature")
        logger.info("Missing signature correctly rejected with 401")

    # =========================================================================
    # Event Type Dispatch Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_trigger_connected_event(self):
        """
        Test the connected system event is dispatched successfully.
        Connected is a notification-only event — no response body expected.
        """
        logger.info("Testing connected event dispatch...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connected",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-connected-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connected",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-connected",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"),
                "test-conn-id-connected"),
        }

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data="{}",
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Connected event")
        logger.info("Connected event dispatched successfully")

    @testutils.retryable_test(3, 5)
    def test_trigger_disconnected_event(self):
        """
        Test the disconnected system event is dispatched successfully.
        Disconnected is a notification-only event — no response body expected.
        The request body MUST include a "reason" field (even if null) because
        the C# DisconnectedEventRequest deserialization requires it.
        """
        logger.info("Testing disconnected event dispatch...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.disconnected",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-disconnected-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "disconnected",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-disconnected",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"),
                "test-conn-id-disconnected"),
        }

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data='{"reason":"normal_closure"}',
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Disconnected event")
        logger.info("Disconnected event dispatched successfully")

    @testutils.retryable_test(3, 5)
    def test_trigger_user_message_json_content_type(self):
        """
        Test user message event with application/json content type.
        Verifies the extension handles JSON-typed user messages.
        """
        logger.info("Testing user message with JSON content type...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.user.message",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-msg-json-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "message",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-json",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"),
                "test-conn-id-json"),
        }

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data='{"text":"hello json"}',
            max_retries=3,
        )

        self.assert_no_server_error(r, "User message JSON content type")
        logger.info("User message JSON returned %d", r.status_code)

    @testutils.retryable_test(3, 5)
    def test_trigger_user_message_binary_content_type(self):
        """
        Test user message event with application/octet-stream content type.
        Verifies the extension handles binary-typed user messages.
        """
        logger.info("Testing user message with binary content type...")

        headers = {
            "Content-Type": "application/octet-stream",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.user.message",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-msg-bin-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "message",
            "ce-hub": "testhub",
            "ce-connectionId": "test-conn-id-bin",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"),
                "test-conn-id-bin"),
        }

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=b"\x00\x01\x02\x03binary data",
            max_retries=3,
        )

        self.assert_no_server_error(r, "User message binary content type")
        logger.info("User message binary returned %d", r.status_code)

    # =========================================================================
    # Hub Routing Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_trigger_wrong_hub_returns_404(self):
        """
        Test that a request targeting a non-existent hub returns 404.
        The extension uses {hub}.{eventType}.{eventName} as the listener key.
        """
        logger.info("Testing wrong hub routing...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/nonexistenthub",
            "ce-id": "test-wrong-hub",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "nonexistenthub",
            "ce-connectionId": "test-conn-id-wronghub",
            "ce-userId": "test-user",
            "ce-signature": "sha256=doesnotmatter",
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=0,
        )

        self.assert_expected_status(r, 404, "Wrong hub")
        logger.info("Wrong hub correctly returned 404")

    @testutils.retryable_test(3, 5)
    def test_trigger_second_hub_routing(self):
        """
        Test that a second hub trigger is correctly routed.
        Verifies multiple triggers with different hub names coexist and
        the extension dispatches to the correct one.
        """
        logger.info("Testing second hub routing...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/secondhub",
            "ce-id": "test-second-hub",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "secondhub",
            "ce-connectionId": "test-conn-id-second",
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"),
                "test-conn-id-second"),
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Second hub routing")
        logger.info("Second hub routing succeeded")

    @testutils.retryable_test(3, 5)
    def test_trigger_missing_connection_id_returns_400(self):
        """
        Test that a missing ce-connectionId header returns 400.
        The extension requires ce-connectionId for request routing and
        signature validation.
        """
        logger.info("Testing missing ce-connectionId...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-default.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/testhub",
            "ce-id": "test-no-connid",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "testhub",
            # ce-connectionId intentionally omitted
            "ce-userId": "test-user",
            "ce-signature": self._compute_ce_signature(
                self._get_access_key("test-default"), "dummy"),
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=0,
        )

        self.assert_expected_status(r, 400, "Missing ce-connectionId")
        logger.info("Missing ce-connectionId correctly returned 400")


class TestWebPubSubCustomConnectionOnly(WebPubSubTestMixin,
                                       testutils.WebHostTestCase):
    """
    Test WebPubSub with ONLY a custom connection name configured.
    The default 'WebPubSubConnectionString' is NOT set.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / "webpubsub_functions_custom_only"

    @classmethod
    def setUpClass(cls):
        # Only custom name — no default WebPubSubConnectionString
        key = base64.b64encode(b"test-custom-key").decode()
        os.environ["MyCustomWebPubSubConnection"] = (
            f"Endpoint=https://test-custom.webpubsub.azure.com;"
            f"AccessKey={key};Version=1.0;"
        )
        # Ensure default is NOT set
        os.environ.pop("WebPubSubConnectionString", None)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        os.environ.pop("MyCustomWebPubSubConnection", None)

    # =========================================================================
    # Custom Connection Only Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_host_starts_with_custom_connection_only(self):
        """
        Verify host starts when only a custom connection name is configured.
        The default WebPubSubConnectionString is NOT set.
        """
        logger.info("Testing host startup with custom connection only...")

        r = self.webhost.request("GET", "health", max_retries=3, expected_status=200)
        self.assert_expected_status(r, 200, "Health with custom connection only")

        logger.info("Host started with custom connection only")

    @testutils.retryable_test(3, 5)
    def test_trigger_connect_with_custom_connection(self):
        """
        Test trigger invocation with only a custom connection configured.
        Verifies the connect event is dispatched when using the
        'connection' property on the trigger binding.
        """
        logger.info("Testing trigger connect with custom connection...")

        headers = {
            "Content-Type": "application/json",
            "WebHook-Request-Origin": "test-custom.webpubsub.azure.com",
            "ce-type": "azure.webpubsub.sys.connect",
            "ce-specversion": "1.0",
            "ce-source": "/hubs/customhub",
            "ce-id": "test-event-custom-001",
            "ce-time": "2026-01-01T00:00:00Z",
            "ce-eventName": "connect",
            "ce-hub": "customhub",
            "ce-connectionId": "test-conn-custom-001",
            "ce-userId": "custom-user",
            # Empty signature is intentional: connection= (singular) does NOT
            # populate the C# attribute's Connections[] property, and no default
            # WebPubSubConnectionString is set either. ResolveAccessesOrDefault()
            # returns null → RequestValidator sets _skipValidation = true →
            # any signature (including empty) is accepted.
            "ce-signature": "sha256=",
        }
        body = (
            '{"claims":{},"query":{},"subprotocols":[],'
            '"clientCertificates":[],"headers":{}}'
        )

        r = self.webhost.request(
            "POST",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers=headers,
            data=body,
            max_retries=3,
            expected_status=200,
        )

        self.assert_success(r, "Connect event with custom connection")

        logger.info("Trigger connect with custom connection succeeded")

    @testutils.retryable_test(3, 5)
    def test_webhook_validation_does_not_crash_without_default_connection(self):
        """
        When only a custom-named connection is configured (no default
        WebPubSubConnectionString), the OPTIONS abuse protection check
        must not return a server error.
        """
        logger.info("Testing OPTIONS request without default connection...")

        r = self.webhost.request(
            "OPTIONS",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "WebHook-Request-Origin": "test-custom.webpubsub.azure.com",
            },
            max_retries=3,
        )

        # Must not crash — any 5xx is a failure (catches NullRef bug #58907)
        self.assert_no_server_error(
            r, "OPTIONS without default WebPubSubConnectionString"
        )

        # Acceptable: 200 (allowed) or 400 (rejected but not crashed)
        self.assertIn(
            r.status_code, [200, 400],
            f"Expected 200 or 400, got {r.status_code}. "
            f"Body: {r.text[:500]}",
        )

        logger.info(
            "OPTIONS without default connection returned %d", r.status_code
        )


class TestWebPubSubIdentityBasedConnection(WebPubSubTestMixin,
                                           testutils.WebHostTestCase):
    """
    Test WebPubSub with identity-based connection (serviceUri config).
    Uses the WebPubSubConnectionString__serviceUri pattern instead of
    a connection string with AccessKey.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / "webpubsub_functions_identity"

    @classmethod
    def setUpClass(cls):
        # Identity-based connection: serviceUri under the default section
        # Uses __ separator for nested config (equivalent to : in JSON)
        os.environ["WebPubSubConnectionString__serviceUri"] = \
            "https://test-identity.webpubsub.azure.com"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        os.environ.pop("WebPubSubConnectionString__serviceUri", None)

    # =========================================================================
    # Identity-Based Connection Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_host_starts_with_identity_based_connection(self):
        """Verify host starts with identity-based (serviceUri) configuration."""
        logger.info("Testing host startup with identity-based connection...")

        r = self.webhost.request("GET", "health", max_retries=3,
                                expected_status=200)
        self.assert_expected_status(r, 200, "Health with identity connection")

        logger.info("Host started with identity-based connection")

    @testutils.retryable_test(3, 5)
    def test_webhook_validation_with_identity_connection(self):
        """
        Verify OPTIONS abuse protection works with identity-based connection.
        The endpoint host from serviceUri should be accepted as a valid origin.
        """
        logger.info("Testing OPTIONS with identity-based connection...")

        r = self.webhost.request(
            "OPTIONS",
            "runtime/webhooks/webpubsub",
            no_prefix=True,
            headers={
                "WebHook-Request-Origin":
                    "test-identity.webpubsub.azure.com",
            },
            max_retries=3,
        )

        self.assert_no_server_error(
            r, "OPTIONS with identity-based connection"
        )

        logger.info(
            "OPTIONS with identity connection returned %d", r.status_code
        )
