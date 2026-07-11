# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import os
import time

import redis

from tests.utils import testutils

logger = logging.getLogger(__name__)

# Keys / channel shared with redis_functions/function_app.py
LIST_KEY = "e2e-list-test"
STREAM_KEY = "e2e-stream-test"
PUBSUB_CHANNEL = "e2e-pubsub-test"


def _redis_client(max_retries: int = 5, retry_delay: int = 3) -> redis.Redis:
    """Return a redis-py client connected to the local emulator."""
    host = os.environ.get("RedisHost", "localhost")
    port = int(os.environ.get("RedisPort", "6379"))

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            client = redis.Redis(host=host, port=port, decode_responses=True)
            client.ping()
            return client
        except Exception as e:  # noqa: BLE001
            last_error = e
            logger.warning(
                f"Redis connection attempt {attempt}/{max_retries} "
                f"failed: {e}"
            )
            if attempt < max_retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Failed to connect to Redis after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


class TestRedisFunctions(testutils.WebHostTestCase):
    """Test Redis triggers and input/output bindings against a local Redis.

    Trigger tests seed Redis via the redis-py client (LPUSH / XADD / PUBLISH)
    and verify the trigger functions processed the data by reading it back
    from the blob they persist to. Binding tests drive an HTTP-triggered
    Redis output binding (SET) and read the value back through a Redis input
    binding (GET).
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'redis_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['redis']

    @testutils.retryable_test(3, 5)
    def test_redis_list_trigger(self):
        """LPUSH a value -> redis_list_trigger -> blob -> HTTP verify."""
        value = f"list-{round(time.time())}"

        client = _redis_client()
        logger.info("Pushing value to Redis list...")
        client.lpush(LIST_KEY, value)

        r = self.webhost.wait_and_request('GET', 'get_redis_list_triggered',
                                          wait_time=15,
                                          max_retries=10,
                                          expected_status=200)
        self.assertEqual(r.text, value)

    @testutils.retryable_test(3, 5)
    def test_redis_stream_trigger(self):
        """XADD an entry -> redis_stream_trigger -> blob -> HTTP verify."""
        value = f"stream-{round(time.time())}"

        client = _redis_client()
        logger.info("Adding entry to Redis stream...")
        client.xadd(STREAM_KEY, {"payload": value})

        r = self.webhost.wait_and_request('GET', 'get_redis_stream_triggered',
                                          wait_time=15,
                                          max_retries=10,
                                          expected_status=200)
        # The stream entry is delivered as a serialized object; assert the
        # payload we added is present in the processed result.
        self.assertIn(value, r.text)

    @testutils.retryable_test(3, 5)
    def test_redis_pubsub_trigger(self):
        """PUBLISH a message -> redis_pubsub_trigger -> blob -> HTTP verify.

        Pub/Sub requires an active subscriber at publish time, so publish
        repeatedly until the trigger persists the message (or timeout).
        """
        value = f"pubsub-{round(time.time())}"

        client = _redis_client()
        logger.info("Publishing message to Redis channel...")

        deadline = time.time() + 60
        last_response = None
        while time.time() < deadline:
            client.publish(PUBSUB_CHANNEL, value)
            try:
                r = self.webhost.request('GET', 'get_redis_pubsub_triggered',
                                         max_retries=1)
                last_response = r
                if r.status_code == 200 and r.text == value:
                    return
            except Exception as e:  # noqa: BLE001
                logger.info(f"Waiting for pubsub trigger: {e}")
            time.sleep(3)

        self.fail(
            "Redis pubsub trigger did not process the message in time. "
            f"Last response: "
            f"{getattr(last_response, 'text', None)!r}"
        )

    @testutils.retryable_test(3, 5)
    def test_redis_input_output_binding(self):
        """SET via output binding -> GET via input binding round-trip."""
        key = f"e2e-io-{round(time.time())}"
        value = f"value-{round(time.time())}"

        # Output binding: SET <key> <value>
        logger.info("Setting key via Redis output binding...")
        r = self.webhost.request('POST', 'redis_set',
                                 data=f"{key} {value}",
                                 max_retries=3,
                                 expected_status=200)
        self.assertEqual(r.text, 'OK')

        # Input binding: GET <key>
        logger.info("Reading key via Redis input binding...")
        r = self.webhost.wait_and_request('GET', f'redis_get/{key}',
                                          wait_time=5,
                                          max_retries=10,
                                          expected_status=200)
        self.assertEqual(r.text, value)
