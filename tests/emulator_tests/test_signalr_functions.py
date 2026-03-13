# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
SignalR Service bindings emulator tests.

Tests for:
- signalRConnectionInfo input binding (negotiate)
- signalR output binding (broadcast, send to user/group, group management)
- signalRTrigger (connection and message events)
"""
import logging
import time

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestSignalRFunctions(testutils.WebHostTestCase):
    """Test cases for SignalR Service bindings."""

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'signalr_functions'

    # =========================================================================
    # Negotiate (Connection Info Input Binding) Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_negotiate_returns_connection_info(self):
        """Test that negotiate endpoint returns valid connection info."""
        logger.info("Testing negotiate endpoint...")

        r = self.webhost.request(
            'POST', 'negotiate', max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        # Parse the connection info
        connection_info = r.json()

        # Verify required fields are present
        self.assertIn('url', connection_info,
                      "Connection info should contain 'url'")
        self.assertIn('accessToken', connection_info,
                      "Connection info should contain 'accessToken'")

        # URL should be a valid SignalR endpoint
        self.assertTrue(connection_info['url'].startswith('http'),
                        "URL should be a valid HTTP endpoint")

        # Access token should be non-empty
        self.assertTrue(len(connection_info['accessToken']) > 0,
                        "Access token should not be empty")

        logger.info("Negotiate returned URL: %s", connection_info['url'])

    @testutils.retryable_test(3, 5)
    def test_negotiate_with_userid_header(self):
        """Test negotiate with userId from header."""
        logger.info("Testing negotiate with userId header...")

        test_user_id = "test-user-123"

        r = self.webhost.request(
            'POST', 'negotiate_with_userid',
            headers={'x-ms-signalr-userid': test_user_id},
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        connection_info = r.json()
        self.assertIn('url', connection_info)
        self.assertIn('accessToken', connection_info)

        logger.info("Negotiate with userId returned successfully")

    # =========================================================================
    # Output Binding Tests (Send Messages)
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_broadcast_message(self):
        """Test broadcasting a message to all clients."""
        logger.info("Testing broadcast message...")

        test_message = "Hello broadcast %d" % int(time.time())

        r = self.webhost.request(
            'POST', 'broadcast', data=test_message,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)
        self.assertIn('broadcast', r.text.lower())

        logger.info("Broadcast message sent successfully")

    @testutils.retryable_test(3, 5)
    def test_send_to_user(self):
        """Test sending a message to a specific user."""
        logger.info("Testing send to user...")

        payload = {
            'userId': 'user-456',
            'message': 'Hello user %d' % int(time.time())
        }

        r = self.webhost.request(
            'POST', 'send_to_user', json=payload,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)
        self.assertIn('user-456', r.text)

        logger.info("Send to user completed successfully")

    def test_send_to_user_missing_fields(self):
        """Test send to user with missing required fields."""
        logger.info("Testing send to user with missing fields...")

        # Missing message
        payload = {'userId': 'user-456'}

        r = self.webhost.request('POST', 'send_to_user', json=payload,
                                 max_retries=1)

        self.assertEqual(r.status_code, 400)
        error_response = r.json()
        self.assertIn('error', error_response)

        logger.info("Send to user correctly rejected missing fields")

    @testutils.retryable_test(3, 5)
    def test_send_to_group(self):
        """Test sending a message to a group."""
        logger.info("Testing send to group...")

        payload = {
            'groupName': 'test-group',
            'message': 'Hello group %d' % int(time.time())
        }

        r = self.webhost.request(
            'POST', 'send_to_group', json=payload,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)
        self.assertIn('test-group', r.text)

        logger.info("Send to group completed successfully")

    # =========================================================================
    # Group Management Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_add_user_to_group(self):
        """Test adding a user to a group."""
        logger.info("Testing add user to group...")

        payload = {
            'userId': 'user-789',
            'groupName': 'premium-users'
        }

        r = self.webhost.request(
            'POST', 'add_to_group', json=payload,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)
        self.assertIn('user-789', r.text)
        self.assertIn('premium-users', r.text)

        logger.info("Add user to group completed successfully")

    @testutils.retryable_test(3, 5)
    def test_remove_user_from_group(self):
        """Test removing a user from a group."""
        logger.info("Testing remove user from group...")

        payload = {
            'userId': 'user-789',
            'groupName': 'premium-users'
        }

        r = self.webhost.request(
            'POST', 'remove_from_group', json=payload,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)
        self.assertIn('user-789', r.text)
        self.assertIn('premium-users', r.text)

        logger.info("Remove user from group completed successfully")

    def test_group_management_missing_fields(self):
        """Test group management with missing required fields."""
        logger.info("Testing group management with missing fields...")

        # Missing groupName
        payload = {'userId': 'user-789'}

        r = self.webhost.request('POST', 'add_to_group', json=payload,
                                 max_retries=1)

        self.assertEqual(r.status_code, 400)
        error_response = r.json()
        self.assertIn('error', error_response)

        logger.info("Group management correctly rejected missing fields")

    # =========================================================================
    # Edge Case Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_broadcast_empty_message(self):
        """Test broadcasting an empty message."""
        logger.info("Testing broadcast empty message...")

        r = self.webhost.request(
            'POST', 'broadcast', data='',
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        logger.info("Broadcast empty message handled")

    @testutils.retryable_test(3, 5)
    def test_broadcast_unicode_message(self):
        """Test broadcasting a message with unicode characters."""
        logger.info("Testing broadcast unicode message...")

        # Message with various unicode characters
        test_message = "Hello 世界 🌍 مرحبا שלום"

        r = self.webhost.request(
            'POST', 'broadcast',
            data=test_message.encode('utf-8'),
            headers={'Content-Type': 'text/plain; charset=utf-8'},
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        logger.info("Broadcast unicode message handled")

    @testutils.retryable_test(3, 5)
    def test_broadcast_large_message(self):
        """Test broadcasting a large message."""
        logger.info("Testing broadcast large message...")

        # Create a message ~10KB in size
        large_message = "x" * 10000

        r = self.webhost.request(
            'POST', 'broadcast', data=large_message,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        logger.info("Broadcast large message handled")

    @testutils.retryable_test(3, 5)
    def test_send_to_user_special_characters_in_userid(self):
        """Test sending to a user with special characters in userId."""
        logger.info("Testing send to user with special characters...")

        payload = {
            'userId': 'user@example.com',
            'message': 'Test message'
        }

        r = self.webhost.request(
            'POST', 'send_to_user', json=payload,
            max_retries=3, expected_status=200)

        self.assertEqual(r.status_code, 200)

        logger.info("Send to user with special characters handled")

    def test_invalid_json_payload(self):
        """Test endpoints with invalid JSON payload."""
        logger.info("Testing invalid JSON payload...")

        r = self.webhost.request(
            'POST', 'send_to_user',
            data='not valid json',
            headers={'Content-Type': 'application/json'},
            max_retries=1)

        self.assertEqual(r.status_code, 400)
        error_response = r.json()
        self.assertIn('error', error_response)

        logger.info("Invalid JSON correctly rejected")

    # =========================================================================
    # Trigger Tests (Connection and Message Events)
    # Note: These tests may require actual SignalR client connections
    # which might not be fully testable with just the emulator
    # =========================================================================

    def test_trigger_endpoints_accessible(self):
        """
        Verify that trigger helper endpoints are accessible.

        Note: The actual trigger tests require SignalR clients to connect
        and send messages. This test just verifies the helper endpoints work.
        """
        logger.info("Testing trigger helper endpoints...")

        # These endpoints read from blob storage where triggers write results
        # They may return 404 if no events have been received yet
        endpoints = ['get_connected_event', 'get_disconnected_event',
                     'get_message_event']
        for endpoint in endpoints:
            r = self.webhost.request('GET', endpoint, max_retries=1)
            # Either 200 (event found) or 404 (no event yet) is acceptable
            self.assertIn(r.status_code, [200, 404],
                          "Endpoint %s should return 200 or 404" % endpoint)

        logger.info("Trigger helper endpoints are accessible")
