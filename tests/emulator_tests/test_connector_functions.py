# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tests for Connector trigger extension.

These tests verify Connector trigger functionality using webhook-based HTTP POST
invocations. No real connector resource is required - tests are self-sufficient
(same approach as WebPubSub webhook-based tests).

The Connector trigger receives JSON payloads at:
  runtime/webhooks/connector?functionName=<name>

Test coverage:
1. Basic trigger - simple JSON payload
2. Nested object payload
3. Array payload
4. Payload processing/transformation
5. Error cases - invalid content type, missing function name, non-existent function
6. Large payload handling
"""
import json
import logging
import time
import uuid

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestConnectorFunctions(testutils.WebHostTestCase):
    """Test Connector Trigger extension via webhook invocation.

    Each test case follows this pattern:
    1. POST JSON payload to the connector webhook endpoint
    2. Wait for function to process and write result to blob storage
    3. Retrieve result via HTTP trigger and verify
    """

    # Connector webhook endpoint for local testing
    CONNECTOR_WEBHOOK_PATH = 'runtime/webhooks/connector'

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'connector_functions'

    def _send_connector_event(self, function_name: str, payload: dict) -> object:
        """Send a JSON payload to a Connector trigger function via webhook.

        Args:
            function_name: Name of the Connector trigger function
            payload: The JSON payload to send

        Returns:
            The HTTP response object
        """
        headers = {
            'Content-Type': 'application/json'
        }

        path = f"{self.CONNECTOR_WEBHOOK_PATH}?functionName={function_name}"

        r = self.webhost.request(
            'POST', path,
            data=json.dumps(payload),
            headers=headers,
            no_prefix=True,
            max_retries=3,
            expected_status=202
        )
        self.assertIsNotNone(r)
        return r

    # =========================================================================
    # Basic Connector Trigger Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_basic(self):
        """Test basic Connector trigger with a simple JSON payload."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'message': 'Hello from connector test',
            'value': 42
        }

        logger.info(f"Sending basic connector event: {test_id}")
        self._send_connector_event('connector_trigger_basic', payload)

        # Wait for trigger to process and write to blob
        r = self.webhost.wait_and_request(
            'GET', 'get_connector_basic',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['payload']['id'], test_id)
        self.assertEqual(result['payload']['message'], 'Hello from connector test')
        self.assertEqual(result['payload']['value'], 42)
        self.assertGreater(result['payload_length'], 0)

    # =========================================================================
    # Nested Object Payload Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_nested_payload(self):
        """Test Connector trigger with nested JSON objects."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'metadata': {
                'source': 'office365',
                'timestamp': '2026-01-01T00:00:00Z',
                'correlation_id': str(uuid.uuid4())
            },
            'body': {
                'subject': 'Test Email',
                'from': 'sender@example.com',
                'to': ['recipient@example.com'],
                'content': 'This is a test email body'
            }
        }

        logger.info(f"Sending nested connector event: {test_id}")
        self._send_connector_event('connector_trigger_nested', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_nested',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertTrue(result['has_metadata'])
        self.assertTrue(result['has_body'])
        self.assertEqual(result['payload']['id'], test_id)
        self.assertEqual(result['payload']['metadata']['source'], 'office365')
        self.assertEqual(result['payload']['body']['subject'], 'Test Email')

    # =========================================================================
    # Array Payload Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_array_payload(self):
        """Test Connector trigger with array payload."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'items': [
                {'name': 'item1', 'value': 'first'},
                {'name': 'item2', 'value': 'second'},
                {'name': 'item3', 'value': 'third'}
            ]
        }

        logger.info(f"Sending array connector event: {test_id}")
        self._send_connector_event('connector_trigger_array', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_array',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['item_count'], 3)
        self.assertEqual(result['payload']['items'][0]['name'], 'item1')
        self.assertEqual(result['payload']['items'][2]['value'], 'third')

    # =========================================================================
    # Payload Processing Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_process_payload(self):
        """Test Connector trigger that processes/transforms the payload."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'eventType': 'Microsoft.Office365.NewEmail',
            'source': '/connectors/office365/email',
            'subject': 'New email received',
            'data': {
                'emailId': 'msg-123',
                'sender': 'test@example.com'
            }
        }

        logger.info(f"Sending process connector event: {test_id}")
        self._send_connector_event('connector_trigger_process', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_process',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['event_type'], 'Microsoft.Office365.NewEmail')
        self.assertEqual(result['source'], '/connectors/office365/email')
        self.assertIn('id', result['processed_fields'])
        self.assertIn('eventType', result['processed_fields'])
        self.assertIn('source', result['processed_fields'])
        self.assertEqual(result['field_count'], 5)

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_invalid_content_type(self):
        """Test that non-JSON content type is rejected."""
        path = f"{self.CONNECTOR_WEBHOOK_PATH}?functionName=connector_trigger_basic"

        r = self.webhost.request(
            'POST', path,
            data='plain text body',
            headers={'Content-Type': 'text/plain'},
            no_prefix=True)

        # Non-JSON content type is rejected (400 - invalid JSON body)
        self.assertIn(r.status_code, (400, 415))

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_missing_function_name(self):
        """Test that missing functionName parameter returns 400."""
        payload = {'id': 'test', 'message': 'no function name'}

        r = self.webhost.request(
            'POST', self.CONNECTOR_WEBHOOK_PATH,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            no_prefix=True)

        # Missing functionName should return 400
        self.assertEqual(r.status_code, 400)

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_nonexistent_function(self):
        """Test that non-existent function name returns 404."""
        payload = {'id': 'test', 'message': 'unknown function'}
        path = f"{self.CONNECTOR_WEBHOOK_PATH}?functionName=nonexistent_function"

        r = self.webhost.request(
            'POST', path,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            no_prefix=True)

        # Non-existent function should return 404
        self.assertEqual(r.status_code, 404)

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_invalid_method(self):
        """Test that GET method is rejected (only POST/PUT allowed)."""
        path = f"{self.CONNECTOR_WEBHOOK_PATH}?functionName=connector_trigger_basic"

        r = self.webhost.request(
            'GET', path,
            no_prefix=True)

        # GET method should be rejected with 405
        self.assertEqual(r.status_code, 405)

    # =========================================================================
    # Large Payload Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_large_payload(self):
        """Test Connector trigger with a large JSON payload."""
        test_id = str(uuid.uuid4())
        # Create a payload with many items (but under 10MB limit)
        large_items = [
            {'index': i, 'data': f'item-data-{i}-' + 'x' * 100}
            for i in range(100)
        ]
        payload = {
            'id': test_id,
            'items': large_items
        }

        logger.info(f"Sending large connector event: {test_id} "
                    f"(~{len(json.dumps(payload))} bytes)")
        self._send_connector_event('connector_trigger_array', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_array',
            wait_time=3,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['item_count'], 100)

    # =========================================================================
    # Special Characters Tests
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_special_characters(self):
        """Test Connector trigger with special characters in payload."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'message': 'Special chars: <>&"\'\\/ \t\n emoji: 🎉',
            'unicode': '日本語テスト',
            'value': 0
        }

        logger.info(f"Sending special chars connector event: {test_id}")
        self._send_connector_event('connector_trigger_basic', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_basic',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['payload']['id'], test_id)
        self.assertEqual(result['payload']['unicode'], '日本語テスト')

    # =========================================================================
    # Body Shape Tests - collection vs single item
    # Connectors can send two body shapes:
    #   {"body": {"value": [...]}}  - collection of items
    #   {"body": {...item...}}      - single item
    # =========================================================================

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_body_collection(self):
        """Test Connector trigger with collection body: {"body": {"value": [...]}}."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'body': {
                'value': [
                    {'emailId': 'msg-001', 'subject': 'First email', 'from': 'a@example.com'},
                    {'emailId': 'msg-002', 'subject': 'Second email', 'from': 'b@example.com'},
                    {'emailId': 'msg-003', 'subject': 'Third email', 'from': 'c@example.com'}
                ]
            }
        }

        logger.info(f"Sending collection body connector event: {test_id}")
        self._send_connector_event('connector_trigger_body', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_body',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['body_type'], 'collection')
        self.assertEqual(result['item_count'], 3)
        self.assertEqual(result['items'][0]['emailId'], 'msg-001')
        self.assertEqual(result['items'][1]['subject'], 'Second email')
        self.assertEqual(result['items'][2]['from'], 'c@example.com')

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_body_single_item(self):
        """Test Connector trigger with single item body: {"body": {...item...}}."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'body': {
                'subject': 'Important Email',
                'from': 'sender@example.com',
                'to': 'recipient@example.com',
                'receivedDateTime': '2026-05-21T14:00:00Z',
                'importance': 'high',
                'hasAttachments': False
            }
        }

        logger.info(f"Sending single item body connector event: {test_id}")
        self._send_connector_event('connector_trigger_body', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_body',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['body_type'], 'single')
        self.assertEqual(result['item_count'], 1)
        self.assertEqual(result['items'][0]['subject'], 'Important Email')
        self.assertEqual(result['items'][0]['from'], 'sender@example.com')
        self.assertEqual(result['items'][0]['importance'], 'high')
        self.assertFalse(result['items'][0]['hasAttachments'])

    @testutils.retryable_test(3, 5)
    def test_connector_trigger_body_empty_collection(self):
        """Test Connector trigger with empty collection: {"body": {"value": []}}."""
        test_id = str(uuid.uuid4())
        payload = {
            'id': test_id,
            'body': {
                'value': []
            }
        }

        logger.info(f"Sending empty collection body connector event: {test_id}")
        self._send_connector_event('connector_trigger_body', payload)

        r = self.webhost.wait_and_request(
            'GET', 'get_connector_body',
            wait_time=2,
            max_retries=10,
            expected_status=200)

        result = json.loads(r.text)

        self.assertTrue(result['received'])
        self.assertEqual(result['body_type'], 'collection')
        self.assertEqual(result['item_count'], 0)
        self.assertEqual(result['items'], [])
