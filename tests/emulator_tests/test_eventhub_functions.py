# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import sys
import time

from unittest import skipIf

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestEventHubFunctions(testutils.WebHostTestCase):
    """Test EventHub Trigger and Output Bindings (cardinality: one).

    Each testcase consists of 3 part:
    1. An eventhub_output HTTP trigger for generating EventHub event
    2. An actual eventhub_trigger EventHub trigger for storing event into blob
    3. A get_eventhub_triggered HTTP trigger for retrieving event info blob
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    def test_eventhub_trigger(self):
        # Generate a unique event body for the EventHub event
        data = str(round(time.time()))
        doc = {'id': data}

        # Invoke eventhub_output HttpTrigger to generate an EventHub Event
        logger.info("Generating EventHub event...")
        r = self.webhost.request('POST', 'eventhub_output',
                                data=json.dumps(doc),
                                max_retries=3,
                                expected_status=200)
        self.assertEqual(r.text, 'OK')

        # Wait for eventhub_trigger to execute and convert event into blob
        logger.info("Waiting for EventHub trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_eventhub_triggered',
                                         wait_time=10,  # EventHub needs more time
                                         max_retries=10,
                                         expected_status=200)
        
        response = r.json()

        # Check if the event body matches the initial data
        self.assertEqual(response, doc)

    @skipIf(sys.version_info.minor == 7,
            "Using azure-eventhub SDK with the EventHub Emulator"
            "requires Python 3.8+")
    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger_with_metadata(self):
        # Generate a unique event body for EventHub event
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        # Invoke metadata_output HttpTrigger to generate an EventHub event from azure-eventhub SDK
        logger.info("Generating EventHub event with metadata...")
        r = self.webhost.request('POST', 'metadata_output',
                                data=json.dumps(req_body),
                                max_retries=3,
                                expected_status=200)
        self.assertIn('OK', r.text)

        # Wait for eventhub_trigger to execute and convert event metadata into blob
        logger.info("Waiting for EventHub metadata trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_metadata_triggered',
                                         wait_time=10,  # EventHub needs more time
                                         max_retries=10,
                                         expected_status=200)

        # Check if the event body matches the unique random_number
        event = r.json()
        self.assertEqual(event['body'], random_number)

        # EventhubEvent property check
        # Reenable these lines after enqueued_time property is fixed
        # enqueued_time = parser.isoparse(event['enqueued_time'])
        # self.assertIsNotNone(enqueued_time)
        self.assertIsNone(event['partition_key'])  # There's only 1 partition
        self.assertGreaterEqual(event['sequence_number'], 0)
        self.assertIsNotNone(event['offset'])

        # Check if the event contains proper metadata fields
        self.assertIsNotNone(event['metadata'])
        metadata = event['metadata']
        sys_props = metadata['SystemProperties']
        self.assertIsNone(sys_props['PartitionKey'])
        self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
        self.assertIsNotNone(sys_props['Offset'])
