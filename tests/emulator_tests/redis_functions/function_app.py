# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Redis E2E Test Functions for Python
Uses the v2 programming model with decorators.

Covers the Redis extension surface (inspired by the extension's own dotnet
integration tests):
  - RedisListTrigger    (LPUSH -> trigger)
  - RedisStreamTrigger  (XADD  -> trigger)
  - RedisPubSubTrigger  (PUBLISH -> trigger)
  - Redis input binding  (GET)
  - Redis output binding (SET)

Trigger functions persist the received value to a storage blob; companion
HTTP functions read the blob back so tests can assert what was processed
(the established pattern used by the other emulator test apps).
"""

import logging

import azure.functions as func

app = func.FunctionApp()

# Connection app-setting name expected by the Redis bindings. Its value is a
# StackExchange.Redis connection string (e.g. "localhost:6379"), injected by
# the test harness / CI.
REDIS_CONNECTION = "redisConnectionString"

# Keys / channel used by the E2E test functions.
LIST_KEY = "e2e-list-test"
STREAM_KEY = "e2e-stream-test"
PUBSUB_CHANNEL = "e2e-pubsub-test"


# ---------------------------------------------------------------------------
# List trigger: pops entries from LIST_KEY and stores them into a blob.
# ---------------------------------------------------------------------------
@app.function_name(name="redis_list_trigger")
@app.generic_trigger(
    arg_name="entry",
    type="redisListTrigger",
    connection=REDIS_CONNECTION,
    key=LIST_KEY,
    data_type="string",
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/test-redis-list-triggered.txt",
    connection="AzureWebJobsStorage",
)
def redis_list_trigger(entry: str) -> str:
    logging.info(f"Redis list trigger received entry: {entry}")
    return entry


@app.function_name(name="get_redis_list_triggered")
@app.route(route="get_redis_list_triggered")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/test-redis-list-triggered.txt",
    connection="AzureWebJobsStorage",
)
def get_redis_list_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    return file.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Stream trigger: reads entries from STREAM_KEY and stores them into a blob.
# ---------------------------------------------------------------------------
@app.function_name(name="redis_stream_trigger")
@app.generic_trigger(
    arg_name="entry",
    type="redisStreamTrigger",
    connection=REDIS_CONNECTION,
    key=STREAM_KEY,
    data_type="string",
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/test-redis-stream-triggered.txt",
    connection="AzureWebJobsStorage",
)
def redis_stream_trigger(entry: str) -> str:
    logging.info(f"Redis stream trigger received entry: {entry}")
    return entry


@app.function_name(name="get_redis_stream_triggered")
@app.route(route="get_redis_stream_triggered")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/test-redis-stream-triggered.txt",
    connection="AzureWebJobsStorage",
)
def get_redis_stream_triggered(req: func.HttpRequest,
                               file: func.InputStream) -> str:
    return file.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Pub/Sub trigger: subscribes to PUBSUB_CHANNEL and stores messages in a blob.
# ---------------------------------------------------------------------------
@app.function_name(name="redis_pubsub_trigger")
@app.generic_trigger(
    arg_name="message",
    type="redisPubSubTrigger",
    connection=REDIS_CONNECTION,
    channel=PUBSUB_CHANNEL,
    data_type="string",
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/test-redis-pubsub-triggered.txt",
    connection="AzureWebJobsStorage",
)
def redis_pubsub_trigger(message: str) -> str:
    logging.info(f"Redis pubsub trigger received message: {message}")
    return message


@app.function_name(name="get_redis_pubsub_triggered")
@app.route(route="get_redis_pubsub_triggered")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/test-redis-pubsub-triggered.txt",
    connection="AzureWebJobsStorage",
)
def get_redis_pubsub_triggered(req: func.HttpRequest,
                               file: func.InputStream) -> str:
    return file.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Output binding: HTTP endpoint that SETs a key via the Redis output binding.
# Request body is the command arguments, e.g. "mykey myvalue".
# ---------------------------------------------------------------------------
@app.function_name(name="redis_set")
@app.route(route="redis_set")
@app.generic_output_binding(
    arg_name="item",
    type="redis",
    connection=REDIS_CONNECTION,
    command="SET",
)
def redis_set(req: func.HttpRequest, item: func.Out[str]) -> str:
    body = req.get_body().decode("utf-8")
    logging.info(f"Redis output binding SET: {body}")
    item.set(body)
    return "OK"


# ---------------------------------------------------------------------------
# Input binding: HTTP endpoint that GETs a key via the Redis input binding.
# The key is supplied as a route parameter and bound into the command.
# ---------------------------------------------------------------------------
@app.function_name(name="redis_get")
@app.route(route="redis_get/{key}")
@app.generic_input_binding(
    arg_name="value",
    type="redis",
    connection=REDIS_CONNECTION,
    command="GET {key}",
    data_type="string",
)
def redis_get(req: func.HttpRequest, value: str) -> str:
    return value if value is not None else ""
