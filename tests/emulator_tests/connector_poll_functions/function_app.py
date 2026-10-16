# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Functions exercised against the local Connector Poll protocol emulator."""

import asyncio
import json
import os
from urllib.request import Request, urlopen

import azure.functions as func


app = func.FunctionApp()


def _notify_emulator(path, body):
    request = Request(
        os.environ['CONNECTOR_EMULATOR_URL'] + path,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-connector-emulator': os.environ['CONNECTOR_EMULATOR_CONTROL_TOKEN'],
        },
        method='POST')
    with urlopen(request, timeout=125) as response:
        return json.load(response)


def _process_poll_event(payload):
    event = json.loads(payload)
    outcome = _notify_emulator('/invocations/start', {'payload_id': event['id']})
    succeeded = False
    try:
        if outcome['fail']:
            raise RuntimeError('Intentional Connector emulator invocation failure.')
        result = json.dumps(event)
        succeeded = True
        return result
    finally:
        _notify_emulator('/invocations/complete', {
            'invocation_id': outcome['invocation_id'],
            'body_succeeded': succeeded,
        })


@app.function_name(name='connector_trigger_poll')
@app.generic_trigger(
    arg_name='payload', type='connectorTrigger', deliveryMode='Poll',
    connection='ConnectorEmulator', triggerConfigName='poll',
    cardinality=func.Cardinality.ONE, maxBatchSize=1, maxConcurrentCalls=1)
@app.blob_output(
    arg_name='$return', path='bundle-tests/test-connector-poll.txt',
    connection='AzureWebJobsStorage')
async def connector_trigger_poll(payload: str) -> str:
    return await asyncio.to_thread(_process_poll_event, payload)


@app.function_name(name='connector_trigger_poll_concurrency')
@app.generic_trigger(
    arg_name='payload', type='connectorTrigger', deliveryMode='Poll',
    connection='ConnectorEmulator', triggerConfigName='concurrency',
    cardinality=func.Cardinality.ONE, maxBatchSize=1, maxConcurrentCalls=2)
async def connector_trigger_poll_concurrency(payload: str) -> None:
    await asyncio.to_thread(_process_poll_event, payload)


@app.function_name(name='get_connector_poll')
@app.route(route='get_connector_poll')
@app.blob_input(
    arg_name='file', path='bundle-tests/test-connector-poll.txt',
    connection='AzureWebJobsStorage')
def get_connector_poll(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.function_name(name='connector_trigger_webhook')
@app.generic_trigger(
    arg_name='payload', type='connectorTrigger', deliveryMode='Webhook')
@app.blob_output(
    arg_name='$return', path='bundle-tests/test-connector-webhook-poll.txt',
    connection='AzureWebJobsStorage')
def connector_trigger_webhook(payload: str) -> str:
    return json.dumps(json.loads(payload))


@app.function_name(name='get_connector_webhook')
@app.route(route='get_connector_webhook')
@app.blob_input(
    arg_name='file', path='bundle-tests/test-connector-webhook-poll.txt',
    connection='AzureWebJobsStorage')
def get_connector_webhook(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')
