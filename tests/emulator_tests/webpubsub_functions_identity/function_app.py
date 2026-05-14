# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Azure Functions Web PubSub test app — identity-based connection.

Uses the serviceUri config pattern instead of a connection string
with AccessKey. This validates that the extension loads correctly
with identity-based connection configuration.
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp()

HUB_NAME = "identityhub"


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="system",
    eventName="connect",
)
def on_connect(request: str) -> str:
    """Trigger for connect event using identity-based default connection."""
    logging.info(f"WebPubSub connect event (identity): {request}")
    return json.dumps({"userId": "identity-user"})


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse("OK", status_code=200)
