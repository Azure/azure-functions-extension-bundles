# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import time

from confluent_kafka import Producer
from tests.utils import testutils

logger = logging.getLogger(__name__)


def _produce_kafka_message(topic: str, value: str,
                           broker: str = 'localhost:9092'):
    """Produce a message to a Kafka topic using confluent-kafka."""
    producer = Producer({'bootstrap.servers': broker})
    producer.produce(topic, value=value.encode('utf-8'))
    producer.flush(timeout=10)


class TestKafkaFunctions(testutils.WebHostTestCase):
    """Test Kafka Trigger and Output Bindings.

    Messages are produced directly via the confluent-kafka Python client
    to avoid binding accumulation bugs with kafka_output decorators.
    The trigger functions store results in blob storage or global variables,
    and HTTP functions retrieve the stored results.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'kafka_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['confluent-kafka']

    @testutils.retryable_test(3, 5)
    def test_kafka_trigger(self):
        # Generate a unique event body for the Kafka event
        data = str(round(time.time()))
        doc = {'id': data}

        # Produce a Kafka message directly via confluent-kafka client
        logger.info("Producing Kafka message...")
        _produce_kafka_message('e2e-test-topic', json.dumps(doc))

        # Wait for kafka_trigger to execute and store event into blob
        logger.info("Waiting for Kafka trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_kafka_triggered',
                                         wait_time=15,
                                         max_retries=10,
                                         expected_status=200)

        response = r.json()

        # Check if the event body matches the initial data
        self.assertEqual(response, doc)

    @testutils.retryable_test(3, 5)
    def test_kafka_trigger_with_metadata(self):
        # Generate a unique event body for metadata test
        random_number = str(round(time.time()) % 1000)

        # Produce a Kafka message directly via confluent-kafka client
        logger.info("Producing Kafka message with metadata...")
        _produce_kafka_message('e2e-metadata-topic', random_number)

        # Wait for kafka_metadata_trigger to execute and store metadata
        # in the global variable, then read it via get_kafka_metadata_triggered
        logger.info("Waiting for Kafka metadata trigger to execute...")
        time.sleep(10)
        r = self.webhost.request('GET',
                                'get_kafka_metadata_triggered',
                                max_retries=10,
                                expected_status=200)

        # Parse and verify the response
        event = r.json()

        self.assertIsInstance(event, dict,
                             f"Expected dict, got {type(event)}: {event}")
        self.assertEqual(event['body'], random_number)

        # KafkaEvent property check
        self.assertEqual(event['topic'], 'e2e-metadata-topic')
        self.assertIsNotNone(event['partition'])
        self.assertIsNotNone(event['offset'])
