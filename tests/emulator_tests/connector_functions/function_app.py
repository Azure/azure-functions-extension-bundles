# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Connector trigger functions for emulator tests.

This module contains Azure Functions that test the Connector trigger extension
using webhook-based invocation (no real connector resource required).

The Connector trigger receives JSON payloads via HTTP webhook at:
  runtime/webhooks/connector?functionName=<name>

Test scenarios covered:
1. Basic trigger - receive and echo JSON payload
2. Payload with nested objects
3. Payload with arrays
4. Empty payload handling
5. Large payload handling
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# =============================================================================
# Basic Connector Trigger - echoes received payload to blob storage
# =============================================================================
@app.function_name(name="connector_trigger_basic")
@app.generic_trigger(
    arg_name="payload",
    type="connectorTrigger")
@app.blob_output(arg_name="$return",
                 path="bundle-tests/test-connector-basic.txt",
                 connection="AzureWebJobsStorage")
def connector_trigger_basic(payload: str) -> str:
    """Receive a basic connector trigger payload and write to blob."""
    logging.info("Connector trigger (basic) received payload")
    result = {
        'received': True,
        'payload': json.loads(payload) if payload else None,
        'payload_length': len(payload) if payload else 0
    }
    return json.dumps(result)


@app.function_name(name="get_connector_basic")
@app.route(route="get_connector_basic")
@app.blob_input(arg_name="file",
                path="bundle-tests/test-connector-basic.txt",
                connection="AzureWebJobsStorage")
def get_connector_basic(req: func.HttpRequest,
                        file: func.InputStream) -> str:
    """Retrieve the basic connector trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Connector Trigger with nested objects
# =============================================================================
@app.function_name(name="connector_trigger_nested")
@app.generic_trigger(
    arg_name="payload",
    type="connectorTrigger")
@app.blob_output(arg_name="$return",
                 path="bundle-tests/test-connector-nested.txt",
                 connection="AzureWebJobsStorage")
def connector_trigger_nested(payload: str) -> str:
    """Receive a connector trigger with nested JSON and write to blob."""
    logging.info("Connector trigger (nested) received payload")
    data = json.loads(payload) if payload else {}
    result = {
        'received': True,
        'has_metadata': 'metadata' in data,
        'has_body': 'body' in data,
        'payload': data
    }
    return json.dumps(result)


@app.function_name(name="get_connector_nested")
@app.route(route="get_connector_nested")
@app.blob_input(arg_name="file",
                path="bundle-tests/test-connector-nested.txt",
                connection="AzureWebJobsStorage")
def get_connector_nested(req: func.HttpRequest,
                         file: func.InputStream) -> str:
    """Retrieve the nested connector trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Connector Trigger - body shape detection (value array vs single item)
# Handles two common connector payload shapes:
#   1. {"body": {"value": [...]}}  - collection of items
#   2. {"body": {...item...}}      - single item
# =============================================================================
@app.function_name(name="connector_trigger_body")
@app.generic_trigger(
    arg_name="payload",
    type="connectorTrigger")
@app.blob_output(arg_name="$return",
                 path="bundle-tests/test-connector-body.txt",
                 connection="AzureWebJobsStorage")
def connector_trigger_body(payload: str) -> str:
    """Detect body shape and extract items accordingly."""
    logging.info("Connector trigger (body) received payload")
    data = json.loads(payload) if payload else {}
    body = data.get('body', {})

    if 'value' in body and isinstance(body['value'], list):
        # Collection shape: {"body": {"value": [...]}}
        items = body['value']
        body_type = 'collection'
    else:
        # Single item shape: {"body": {...item...}}
        items = [body] if body else []
        body_type = 'single'

    result = {
        'received': True,
        'body_type': body_type,
        'item_count': len(items),
        'items': items,
        'payload': data
    }
    return json.dumps(result)


@app.function_name(name="get_connector_body")
@app.route(route="get_connector_body")
@app.blob_input(arg_name="file",
                path="bundle-tests/test-connector-body.txt",
                connection="AzureWebJobsStorage")
def get_connector_body(req: func.HttpRequest,
                       file: func.InputStream) -> str:
    """Retrieve the body-shape connector trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Connector Trigger with array payload
# =============================================================================
@app.function_name(name="connector_trigger_array")
@app.generic_trigger(
    arg_name="payload",
    type="connectorTrigger")
@app.blob_output(arg_name="$return",
                 path="bundle-tests/test-connector-array.txt",
                 connection="AzureWebJobsStorage")
def connector_trigger_array(payload: str) -> str:
    """Receive a connector trigger with array payload and write to blob."""
    logging.info("Connector trigger (array) received payload")
    data = json.loads(payload) if payload else {}
    items = data.get('items', [])
    result = {
        'received': True,
        'item_count': len(items),
        'payload': data
    }
    return json.dumps(result)


@app.function_name(name="get_connector_array")
@app.route(route="get_connector_array")
@app.blob_input(arg_name="file",
                path="bundle-tests/test-connector-array.txt",
                connection="AzureWebJobsStorage")
def get_connector_array(req: func.HttpRequest,
                        file: func.InputStream) -> str:
    """Retrieve the array connector trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Connector Trigger - processes payload and returns summary
# =============================================================================
@app.function_name(name="connector_trigger_process")
@app.generic_trigger(
    arg_name="payload",
    type="connectorTrigger")
@app.blob_output(arg_name="$return",
                 path="bundle-tests/test-connector-process.txt",
                 connection="AzureWebJobsStorage")
def connector_trigger_process(payload: str) -> str:
    """Process a connector trigger payload (simulating real processing)."""
    logging.info("Connector trigger (process) received payload")
    data = json.loads(payload) if payload else {}

    # Simulate processing - extract and transform data
    result = {
        'received': True,
        'event_type': data.get('eventType', 'unknown'),
        'source': data.get('source', 'unknown'),
        'processed_fields': list(data.keys()),
        'field_count': len(data),
        'payload': data
    }
    return json.dumps(result)


@app.function_name(name="get_connector_process")
@app.route(route="get_connector_process")
@app.blob_input(arg_name="file",
                path="bundle-tests/test-connector-process.txt",
                connection="AzureWebJobsStorage")
def get_connector_process(req: func.HttpRequest,
                          file: func.InputStream) -> str:
    """Retrieve the processed connector trigger result from blob storage."""
    return file.read().decode('utf-8')
