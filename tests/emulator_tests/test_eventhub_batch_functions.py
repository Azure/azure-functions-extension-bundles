# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import sys
import time
from datetime import datetime
from unittest.case import skipIf

from dateutil import parser
from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestEventHubBatchFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_batch_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple(self):
        NUM_EVENTS = 3
        all_row_keys_seen = dict([(i, True) for i in range(NUM_EVENTS)])
        partition_key = str(round(time.time()))

        docs = []
        for i in range(NUM_EVENTS):
            doc = {'PartitionKey': partition_key, 'RowKey': i}
            docs.append(doc)

        # Send events to EventHub
        logger.info("Sending events to EventHub batch...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', 'eventhub_output_batch',
            data=json.dumps(docs),
            expected_status=200
        )

        row_keys = [i for i in range(NUM_EVENTS)]
        seen = [False] * NUM_EVENTS
        row_keys_seen = dict(zip(row_keys, seen))

        # Wait for trigger to fire and retry request
        logger.info("Waiting for EventHub batch trigger to execute...")
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_eventhub_batch_triggered',
            wait_time=5,
            max_retries=10,
            expected_status=200
        )
        
        entries = r.json()
        for entry in entries:
            self.assertEqual(entry['PartitionKey'], partition_key)
            row_key = entry['RowKey']
            row_keys_seen[row_key] = True

        self.assertDictEqual(all_row_keys_seen, row_keys_seen)

    @skipIf(sys.version_info.minor == 7,
            "Using azure-eventhub SDK with the EventHub Emulator"
            "requires Python 3.8+")
    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple_with_metadata(self):
        # Generate a unique event body for EventHub event
        # Record the start_time and end_time for checking event enqueue time
        start_time = datetime.utcnow()
        count = 10
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        # Invoke metadata_output HttpTrigger to generate an EventHub event from azure-eventhub SDK
        logger.info("Generating EventHub events with metadata...")
        r = testutils.make_request_with_retry(
            self.webhost, 'POST', f'metadata_output_batch?count={count}',
            data=json.dumps(req_body),
            expected_status=200
        )
        self.assertIn('OK', r.text)
        end_time = datetime.utcnow()

        # Wait for metadata_multiple trigger to execute and convert event metadata into blob
        logger.info("Waiting for EventHub metadata trigger to execute...")
        r = testutils.wait_and_retry_request(
            self.webhost, 'GET', 'get_metadata_batch_triggered',
            wait_time=5,
            max_retries=10,
            expected_status=200
        )

        # Check metadata and events length, events should be batched processed
        events = r.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 1)

        # EventhubEvent property check
        for event_index in range(len(events)):
            event = events[event_index]

            # Check if the event is enqueued between start_time and end_time
            enqueued_time = parser.isoparse(event['enqueued_time'])
            self.assertTrue(start_time < enqueued_time < end_time)

            # Check if event properties are properly set
            self.assertIsNone(event['partition_key'])  # only 1 partition
            self.assertGreaterEqual(event['sequence_number'], 0)
            self.assertIsNotNone(event['offset'])

            # Check if event.metadata field is properly set
            self.assertIsNotNone(event['metadata'])
            metadata = event['metadata']
            sys_props_array = metadata['SystemPropertiesArray']
            sys_props = sys_props_array[event_index]
            enqueued_time = parser.isoparse(sys_props['EnqueuedTimeUtc'])

            # Check event trigger time and other system properties
            self.assertTrue(
                start_time.timestamp() < enqueued_time.timestamp()
                < end_time.timestamp())  # NoQA
            self.assertIsNone(sys_props['PartitionKey'])
            self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
            self.assertIsNotNone(sys_props['Offset'])
