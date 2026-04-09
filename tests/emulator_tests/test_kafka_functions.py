# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import os
import time

from confluent_kafka import Producer
from tests.utils import testutils

logger = logging.getLogger(__name__)


def _produce_kafka_message(topic: str, value: str,
                           broker: str = None):
    """Produce a message to a Kafka topic using confluent-kafka."""
    if broker is None:
        broker = os.environ.get('BrokerList', 'localhost:9092')
    producer = Producer({'bootstrap.servers': broker})
    producer.produce(topic, value=value.encode('utf-8'))
    undelivered = producer.flush(timeout=10)
    if undelivered > 0:
        logger.error(
            "Failed to deliver %d Kafka message(s) to topic '%s' within "
            "the flush timeout.",
            undelivered,
            topic,
        )
        raise RuntimeError(
            f"Kafka producer failed to deliver {undelivered} message(s) "
            f"to topic '{topic}' within the flush timeout."
        )


class TestKafkaFunctions(testutils.WebHostTestCase):
    """Test Kafka Trigger and Output Bindings.

    Trigger tests produce messages via the confluent-kafka Python client
    and verify that Kafka trigger functions process them correctly.
    Output binding tests send messages via an HTTP-triggered Kafka output
    binding and verify round-trip delivery through a Kafka trigger.
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
    def test_kafka_output(self):
        """Test Kafka output binding via HTTP trigger → Kafka → trigger → blob.

        1. POST data to kafka_output HTTP endpoint (sends to Kafka via output binding)
        2. kafka_output_trigger picks up the message and stores it in blob
        3. Retrieve from blob via get_kafka_output_triggered and verify
        """
        data = str(round(time.time()))
        doc = {'id': data}

        # Invoke kafka_output HttpTrigger to send message via output binding
        logger.info("Sending Kafka message via output binding...")
        r = self.webhost.request('POST', 'kafka_output',
                                data=json.dumps(doc),
                                max_retries=3,
                                expected_status=200)
        self.assertEqual(r.text, 'OK')

        # Wait for kafka_output_trigger to execute and store event into blob
        logger.info("Waiting for Kafka output trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_kafka_output_triggered',
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
        r = self.webhost.wait_and_request('GET',
                                         'get_kafka_metadata_triggered',
                                         wait_time=15,
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
