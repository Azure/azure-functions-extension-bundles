# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Azure Functions Web PubSub bindings test functions.

Uses generic_trigger since Python v2 SDK doesn't have native WebPubSub
decorators.

These functions test the WebPubSub extension's webhook validation and
trigger dispatch paths. No actual WebPubSub service is needed — the
extension handles OPTIONS (abuse protection) and POST (trigger) requests
directly within the Functions host process.
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp()

# Hub name used across all WebPubSub functions
HUB_NAME = "testhub"

# =============================================================================
# WebPubSub Trigger — system events (connect, connected, disconnected)
# =============================================================================


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="system",
    eventName="connect",
)
def on_connect(request: str) -> str:
    """
    Trigger for connect event using the DEFAULT WebPubSubConnectionString.
    Returns connection response with userId.
    """
    logging.info(f"WebPubSub connect event: {request}")
    return json.dumps({"userId": "test-user"})


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="system",
    eventName="connected",
)
def on_connected(request: str) -> None:
    """Trigger for connected event (no response expected)."""
    logging.info(f"WebPubSub connected event: {request}")


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="system",
    eventName="disconnected",
)
def on_disconnected(request: str) -> None:
    """Trigger for disconnected event (no response expected)."""
    logging.info(f"WebPubSub disconnected event: {request}")


# =============================================================================
# WebPubSub Trigger — user message event
# =============================================================================


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub=HUB_NAME,
    eventType="user",
    eventName="message",
)
def on_message(request: str) -> str:
    """Trigger for user message event. Echoes the message back."""
    logging.info(f"WebPubSub message event: {request}")
    return json.dumps({"message": "echo"})


# =============================================================================
# WebPubSub Trigger — using CUSTOM connection name (connections=[] plural)
# Uses the correct "connections" (plural, array) property which maps to
# the C# attribute's Connections[] and enables per-trigger signature validation.
# =============================================================================


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub="customhub",
    eventType="system",
    eventName="connect",
    connections=["MyCustomWebPubSubConnection"],
)
def on_connect_custom(request: str) -> str:
    """Trigger for connect event using connections= (plural, per-trigger validation)."""
    logging.info(f"WebPubSub connect event (custom conn): {request}")
    return json.dumps({"userId": "custom-user"})


# =============================================================================
# WebPubSub Trigger — using connection= (singular) as many customers do
# The singular "connection" property does NOT map to the C# trigger attribute's
# Connections[] property — it is silently ignored. Validation falls back to the
# default WebPubSubConnectionString. The trigger still routes and invokes correctly.
# =============================================================================


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub="legacyhub",
    eventType="system",
    eventName="connect",
    connection="MyCustomWebPubSubConnection",
)
def on_connect_legacy(request: str) -> str:
    """Trigger using connection= (singular) — validation falls back to default."""
    logging.info(f"WebPubSub connect event (legacy conn): {request}")
    return json.dumps({"userId": "legacy-user"})


# =============================================================================
# WebPubSub Trigger — multiple hubs
# Verifies that multiple triggers with different hub names can coexist.
# =============================================================================


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub="secondhub",
    eventType="system",
    eventName="connect",
)
def on_connect_second_hub(request: str) -> str:
    """Trigger for connect event on a second hub."""
    logging.info(f"WebPubSub connect event (secondhub): {request}")
    return json.dumps({"userId": "second-hub-user"})


@app.generic_trigger(
    arg_name="request",
    type="webPubSubTrigger",
    hub="secondhub",
    eventType="user",
    eventName="message",
)
def on_message_second_hub(request: str) -> str:
    """Trigger for user message on a second hub."""
    logging.info(f"WebPubSub message event (secondhub): {request}")
    return json.dumps({"message": "echo-second-hub"})


# =============================================================================
# WebPubSub Connection Info Input Binding (Negotiate)
# Generates client access URL + JWT token from the connection string.
# This is entirely local computation — no WebPubSub service call needed.
# See: https://learn.microsoft.com/azure/azure-functions/functions-bindings-web-pubsub-input
# =============================================================================

@app.route(route="negotiate", methods=["POST"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="webPubSubConnection",
    hub=HUB_NAME,
    connection="WebPubSubConnectionString",
)
def negotiate(req: func.HttpRequest, connectionInfo: str) -> func.HttpResponse:
    """
    Negotiate endpoint — returns WebPubSub connection info for clients.
    The input binding generates the URL and access token locally from the
    access key in the connection string.
    """
    logging.info("WebPubSub negotiate called")
    return func.HttpResponse(
        connectionInfo,
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="negotiate_with_userid", methods=["POST"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="webPubSubConnection",
    hub=HUB_NAME,
    userId="{headers.x-ms-webpubsub-userid}",
    connection="WebPubSubConnectionString",
)
def negotiate_with_userid(
    req: func.HttpRequest, connectionInfo: str
) -> func.HttpResponse:
    """Negotiate endpoint with userId binding from request header."""
    logging.info("WebPubSub negotiate with userId called")
    return func.HttpResponse(
        connectionInfo,
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="negotiate_custom_conn", methods=["POST"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="webPubSubConnection",
    hub=HUB_NAME,
    connection="MyCustomWebPubSubConnection",
)
def negotiate_custom_conn(
    req: func.HttpRequest, connectionInfo: str
) -> func.HttpResponse:
    """Negotiate endpoint using a custom-named connection setting."""
    logging.info("WebPubSub negotiate (custom conn) called")
    return func.HttpResponse(
        connectionInfo,
        status_code=200,
        mimetype="application/json",
    )


# =============================================================================
# WebPubSub Output Binding (Send Messages)
# =============================================================================


@app.route(route="send_to_group", methods=["POST"])
@app.generic_output_binding(
    arg_name="actions",
    type="webPubSub",
    hub=HUB_NAME,
    connection="WebPubSubConnectionString",
)
def send_to_group(
    req: func.HttpRequest, actions: func.Out[str]
) -> func.HttpResponse:
    """Send a message to a specific group."""
    try:
        body = req.get_json()
        group_name = body.get("groupName")
        message = body.get("message")
    except (ValueError, json.JSONDecodeError):
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json",
        )

    if not group_name or not message:
        return func.HttpResponse(
            json.dumps({"error": "groupName and message required"}),
            status_code=400,
            mimetype="application/json",
        )

    logging.info(f"Sending to group {group_name}: {message}")

    actions.set(json.dumps({
        "actionName": "sendToGroup",
        "group": group_name,
        "data": message,
        "dataType": "text",
    }))

    return func.HttpResponse(
        f"Message sent to group {group_name}", status_code=200
    )


@app.route(route="add_user_to_group", methods=["POST"])
@app.generic_output_binding(
    arg_name="actions",
    type="webPubSub",
    hub=HUB_NAME,
    connection="WebPubSubConnectionString",
)
def add_user_to_group(
    req: func.HttpRequest, actions: func.Out[str]
) -> func.HttpResponse:
    """Add a user to a group."""
    try:
        body = req.get_json()
        user_id = body.get("userId")
        group_name = body.get("groupName")
    except (ValueError, json.JSONDecodeError):
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json",
        )

    if not user_id or not group_name:
        return func.HttpResponse(
            json.dumps({"error": "userId and groupName required"}),
            status_code=400,
            mimetype="application/json",
        )

    logging.info(f"Adding user {user_id} to group {group_name}")

    actions.set(json.dumps({
        "actionName": "addUserToGroup",
        "userId": user_id,
        "group": group_name,
    }))

    return func.HttpResponse(
        f"User {user_id} added to group {group_name}", status_code=200
    )


# =============================================================================
# Helper HTTP endpoint to verify host startup health
# =============================================================================


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint to verify the host started successfully."""
    return func.HttpResponse("OK", status_code=200)
