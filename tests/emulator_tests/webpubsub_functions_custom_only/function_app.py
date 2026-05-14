# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Azure Functions Web PubSub test app — CUSTOM connection name ONLY.

This function app is specifically designed to reproduce the NRE bug in
WebPubSub extension 1.10.0 (ICM 21000000992543). It uses ONLY a custom
connection name, with NO default 'WebPubSubConnectionString' configured.
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

HUB_NAME = "customhub"


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="system",
    eventName="connect",
    connection="MyCustomWebPubSubConnection",
)
def on_connect(request: str) -> str:
    """
    Trigger for connect event using CUSTOM connection name only.
    No default WebPubSubConnectionString is configured.
    """
    logging.info(f"WebPubSub connect event: {request}")
    return json.dumps({"userId": "test-user"})


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse("OK", status_code=200)
