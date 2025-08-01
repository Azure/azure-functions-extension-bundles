# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import time

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestQueueFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'queue_functions'

    def test_queue_basic(self):
        # Send message to queue
        logger.info("Sending message to queue...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', 'put_queue',
            data='test-message',
            expected_status=200
        )
        self.assertEqual(r.text, 'OK')

        # Wait for queue_trigger to process the queue item
        logger.info("Waiting for queue trigger to process message...")
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_queue_blob',
            wait_time=2,
            max_retries=3,
            expected_status=200
        )
        
        msg_info = r.json()

        self.assertIn('queue', msg_info)
        msg = msg_info['queue']

        self.assertEqual(msg['body'], 'test-message')
        for attr in {'id', 'expiration_time', 'insertion_time',
                     'time_next_visible', 'pop_receipt', 'dequeue_count'}:
            self.assertIsNotNone(msg.get(attr))

    def test_queue_return(self):
        # Send message with return value test
        logger.info("Testing queue return value...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', 'put_queue_return',
            data='test-message-return',
            expected_status=200
        )

        # Wait for queue_trigger to process the queue item
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_queue_blob_return',
            wait_time=2,
            max_retries=3,
            expected_status=200
        )
        self.assertEqual(r.text, 'test-message-return')

    def test_queue_message_object_return(self):
        # Send message object return test
        logger.info("Testing queue message object return...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', 'put_queue_message_return',
            data='test-message-object-return',
            expected_status=200
        )

        # Wait for queue_trigger to process the queue item
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_queue_blob_message_return',
            wait_time=2,
            max_retries=3,
            expected_status=200
        )
        self.assertEqual(r.text, 'test-message-object-return')

    def test_queue_untyped_return(self):
        r = self.webhost.request('POST', 'put_queue_untyped_return',
                                 data='test-untyped-return')
        self.assertEqual(r.status_code, 200)

        # wait for queue_trigger to process the queue item
        time.sleep(1)

        r = self.webhost.request('GET', 'get_queue_untyped_blob_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-untyped-return')

    def test_queue_return_multiple(self):
        r = self.webhost.request('POST', 'put_queue_return_multiple',
                                 data='foo')
        self.assertTrue(200 <= r.status_code < 300,
                        f"Returned status code {r.status_code}, "
                        "not in the 200-300 range.")

        # wait for queue_trigger to process the queue item
        time.sleep(1)

    def test_queue_return_multiple_outparam(self):
        r = self.webhost.request('POST', 'put_queue_multiple_out',
                                 data='foo')
        self.assertTrue(200 <= r.status_code < 300,
                        f"Returned status code {r.status_code}, "
                        "not in the 200-300 range.")
        self.assertEqual(r.text, 'HTTP response: foo')
