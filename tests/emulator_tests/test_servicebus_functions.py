# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import time

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestServiceBusFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_functions'

    @testutils.retryable_test(3, 5)
    def test_servicebus_basic(self):
        data = str(round(time.time()))
        
        # Send message to Service Bus queue
        logger.info("Sending message to Service Bus queue...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', 'put_message',
            data=data,
            expected_status=200
        )
        self.assertEqual(r.text, 'OK')

        # Wait for Service Bus trigger to process the message with extended retry
        logger.info("Waiting for Service Bus trigger to process message...")
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_servicebus_triggered',
            wait_time=3,
            max_retries=10,  # Service Bus may need more retries
            expected_status=200
        )
        
        msg = r.json()
        self.assertEqual(msg['body'], data)
        
        # Verify all expected Service Bus message attributes are present
        for attr in {'message_id', 'body', 'content_type', 'delivery_count',
                     'expiration_time', 'label', 'partition_key', 'reply_to',
                     'reply_to_session_id', 'scheduled_enqueue_time',
                     'session_id', 'time_to_live', 'to', 'user_properties',
                     'application_properties', 'correlation_id',
                     'dead_letter_error_description', 'dead_letter_reason',
                     'dead_letter_source', 'enqueued_sequence_number',
                     'enqueued_time_utc', 'expires_at_utc', 'locked_until',
                     'lock_token', 'sequence_number', 'state', 'subject',
                     'transaction_partition_key'}:
            self.assertIn(attr, msg)

