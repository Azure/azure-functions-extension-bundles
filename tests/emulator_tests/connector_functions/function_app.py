# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Minimal Webhook functions for bundle-level Connector validation."""

import azure.functions as func


app = func.FunctionApp()


@app.function_name(name='connector_trigger_default')
@app.generic_trigger(arg_name='payload', type='connectorTrigger')
@app.blob_output(
    arg_name='$return', path='bundle-tests/test-connector-default.txt',
    connection='AzureWebJobsStorage')
def connector_trigger_default(payload: str) -> str:
    return payload


@app.function_name(name='get_connector_default')
@app.route(route='get_connector_default')
@app.blob_input(
    arg_name='file', path='bundle-tests/test-connector-default.txt',
    connection='AzureWebJobsStorage')
def get_connector_default(
        req: func.HttpRequest, file: func.InputStream) -> func.HttpResponse:
    return func.HttpResponse(body=file.read(), mimetype='application/json')


@app.function_name(name='connector_trigger_explicit')
@app.generic_trigger(
    arg_name='payload', type='connectorTrigger', deliveryMode='Webhook')
@app.blob_output(
    arg_name='$return', path='bundle-tests/test-connector-explicit.txt',
    connection='AzureWebJobsStorage')
def connector_trigger_explicit(payload: str) -> str:
    return payload


@app.function_name(name='get_connector_explicit')
@app.route(route='get_connector_explicit')
@app.blob_input(
    arg_name='file', path='bundle-tests/test-connector-explicit.txt',
    connection='AzureWebJobsStorage')
def get_connector_explicit(
        req: func.HttpRequest, file: func.InputStream) -> func.HttpResponse:
    return func.HttpResponse(body=file.read(), mimetype='application/json')
