# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import os
import time

import pika

from tests.utils import testutils

logger = logging.getLogger(__name__)


def _produce_rabbitmq_message(queue: str, message: str,
                              host: str = None, port: int = None,
                              max_retries: int = 5, retry_delay: int = 5):
    """Produce a message to a RabbitMQ queue using pika with retry logic."""
    if host is None:
        host = os.environ.get('RabbitMQHost', 'localhost')
    if port is None:
        port = int(os.environ.get('RabbitMQPort', '5672'))

    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            # Declare the queue (creates if not exists)
            channel.queue_declare(queue=queue, durable=False)

            # Publish the message
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=message.encode('utf-8')
            )

            logger.info(f"Sent message to RabbitMQ queue '{queue}': {message}")
            connection.close()
            return
        except Exception as e:
            last_error = e
            logger.warning(
                f"RabbitMQ connection attempt {attempt}/{max_retries} "
                f"failed: {e}"
            )
            if attempt < max_retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Failed to send message to RabbitMQ after {max_retries} "
        f"attempts. Last error: {last_error}"
    )


class TestRabbitMQFunctions(testutils.WebHostTestCase):
    """Test RabbitMQ Trigger and Output Bindings.

    Trigger tests produce messages via the pika Python client
    and verify that RabbitMQ trigger functions process them correctly.
    Output binding tests send messages via an HTTP-triggered RabbitMQ output
    binding and verify round-trip delivery through a RabbitMQ trigger.
    """

    # Queue names used by the E2E test functions
    TRIGGER_QUEUE = 'e2e-test-queue'
    OUTPUT_QUEUE = 'e2e-output-queue'

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'rabbitmq_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['pika']

    @classmethod
    def setUpClass(cls):
        """Pre-create RabbitMQ queues then start the WebHost.

        The RabbitMQ extension uses QueueDeclarePassive, which requires
        queues to already exist when the function host starts. Without
        this step the trigger bindings fail to initialise.
        """
        cls._ensure_rabbitmq_queues()
        super().setUpClass()

    @classmethod
    def _ensure_rabbitmq_queues(cls):
        """Declare RabbitMQ queues so the extension can bind to them."""
        host = os.environ.get('RabbitMQHost', 'localhost')
        port = int(os.environ.get('RabbitMQPort', '5672'))
        credentials = pika.PlainCredentials('guest', 'guest')
        parameters = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            connection_attempts=5,
            retry_delay=3
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=cls.TRIGGER_QUEUE, durable=False)
        channel.queue_declare(queue=cls.OUTPUT_QUEUE, durable=False)
        connection.close()
        logger.info("Pre-created RabbitMQ queues: %s, %s",
                    cls.TRIGGER_QUEUE, cls.OUTPUT_QUEUE)

    @testutils.retryable_test(3, 5)
    def test_rabbitmq_trigger(self):
        """Test RabbitMQ trigger via pika → trigger → blob → HTTP.

        1. Send a JSON document to RabbitMQ via pika client
        2. rabbitmq_trigger picks up the message and stores it in blob
        3. Retrieve from blob via get_rabbitmq_triggered and verify
        """
        # Generate a unique message body
        data = str(round(time.time()))
        doc = {'id': data}

        # Produce a RabbitMQ message directly via pika client
        logger.info("Producing RabbitMQ message...")
        _produce_rabbitmq_message('e2e-test-queue', json.dumps(doc))

        # Wait for rabbitmq_trigger to execute and store message into blob
        logger.info("Waiting for RabbitMQ trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_rabbitmq_triggered',
                                          wait_time=15,
                                          max_retries=10,
                                          expected_status=200)

        response = r.json()

        # Check if the message body matches the initial data
        self.assertEqual(response, doc)

    @testutils.retryable_test(3, 5)
    def test_rabbitmq_output(self):
        """Test RabbitMQ output binding via HTTP → RabbitMQ → trigger → blob.

        1. POST data to rabbitmq_output HTTP endpoint (sends to RabbitMQ via output binding)
        2. rabbitmq_output_trigger picks up the message and stores it in blob
        3. Retrieve from blob via get_rabbitmq_output_triggered and verify
        """
        data = str(round(time.time()))
        doc = {'id': data}

        # Invoke rabbitmq_output HttpTrigger to send message via output binding
        logger.info("Sending RabbitMQ message via output binding...")
        r = self.webhost.request('POST', 'rabbitmq_output',
                                 data=json.dumps(doc),
                                 max_retries=3,
                                 expected_status=200)
        self.assertEqual(r.text, 'OK')

        # Wait for rabbitmq_output_trigger to execute and store message into blob
        logger.info("Waiting for RabbitMQ output trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_rabbitmq_output_triggered',
                                          wait_time=15,
                                          max_retries=10,
                                          expected_status=200)

        response = r.json()

        # Check if the message body matches the initial data
        self.assertEqual(response, doc)
