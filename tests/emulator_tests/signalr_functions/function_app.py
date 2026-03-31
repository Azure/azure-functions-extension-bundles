"""
Azure Functions SignalR Service bindings test functions.

Uses generic_trigger, generic_input_binding, and generic_output_binding
since Python v2 SDK doesn't have native SignalR decorators.
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Hub name used across all SignalR functions
HUB_NAME = "testhub"


# =============================================================================
# SignalR Connection Info Input Binding (Negotiate)
# =============================================================================

@app.route(route="negotiate", methods=["POST"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="signalRConnectionInfo",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def negotiate(req: func.HttpRequest, connectionInfo: str) -> func.HttpResponse:
    """
    Negotiate endpoint - returns SignalR connection info for clients.

    This is the standard negotiate endpoint that SignalR clients call
    to get the service URL and access token.
    """
    logging.info("SignalR negotiate called")
    return func.HttpResponse(
        connectionInfo,
        status_code=200,
        mimetype='application/json'
    )


@app.route(route="negotiate_with_userid", methods=["POST"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="signalRConnectionInfo",
    hubName=HUB_NAME,
    userId="{headers.x-ms-signalr-userid}",
    connectionStringSetting="AzureSignalRConnectionString"
)
def negotiate_with_userid(req: func.HttpRequest, connectionInfo: str) -> func.HttpResponse:
    """
    Negotiate endpoint with userId binding from header.

    The userId is extracted from the x-ms-signalr-userid header
    and included in the generated access token.
    """
    logging.info("SignalR negotiate with userId called")
    return func.HttpResponse(
        connectionInfo,
        status_code=200,
        mimetype='application/json'
    )


# =============================================================================
# SignalR Output Binding (Send Messages)
# =============================================================================

@app.route(route="broadcast", methods=["POST"])
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def broadcast(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """
    Broadcast a message to all connected clients.
    """
    message = req.get_body().decode('utf-8')
    logging.info(f"Broadcasting message: {message}")

    signalRMessages.set(json.dumps({
        'target': 'newMessage',
        'arguments': [message]
    }))

    return func.HttpResponse("Message broadcast", status_code=200)


@app.route(route="send_to_user", methods=["POST"])
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def send_to_user(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """
    Send a message to a specific user by userId.
    """
    try:
        body = req.get_json()
        user_id = body.get('userId')
        message = body.get('message')
    except (ValueError, json.JSONDecodeError) as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )

    if not user_id or not message:
        logging.error("Missing userId or message")
        return func.HttpResponse(
            json.dumps({"error": "userId and message required"}),
            status_code=400,
            mimetype="application/json"
        )

    logging.info(f"Sending message to user {user_id}: {message}")

    signalRMessages.set(json.dumps({
        'userId': user_id,
        'target': 'newMessage',
        'arguments': [message]
    }))

    return func.HttpResponse(f"Message sent to user {user_id}", status_code=200)


@app.route(route="send_to_group", methods=["POST"])
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def send_to_group(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """
    Send a message to all clients in a specific group.
    """
    try:
        body = req.get_json()
        group_name = body.get('groupName')
        message = body.get('message')
    except (ValueError, json.JSONDecodeError) as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )

    if not group_name or not message:
        logging.error("Missing groupName or message")
        return func.HttpResponse(
            json.dumps({"error": "groupName and message required"}),
            status_code=400,
            mimetype="application/json"
        )

    logging.info(f"Sending message to group {group_name}: {message}")

    signalRMessages.set(json.dumps({
        'groupName': group_name,
        'target': 'newMessage',
        'arguments': [message]
    }))

    return func.HttpResponse(f"Message sent to group {group_name}", status_code=200)


# =============================================================================
# SignalR Group Management
# =============================================================================

@app.route(route="add_to_group", methods=["POST"])
@app.generic_output_binding(
    arg_name="signalRGroupActions",
    type="signalR",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def add_to_group(req: func.HttpRequest, signalRGroupActions: func.Out[str]) -> func.HttpResponse:
    """
    Add a user to a group.
    """
    try:
        body = req.get_json()
        user_id = body.get('userId')
        group_name = body.get('groupName')
    except (ValueError, json.JSONDecodeError) as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )

    if not user_id or not group_name:
        logging.error("Missing userId or groupName")
        return func.HttpResponse(
            json.dumps({"error": "userId and groupName required"}),
            status_code=400,
            mimetype="application/json"
        )

    logging.info(f"Adding user {user_id} to group {group_name}")

    signalRGroupActions.set(json.dumps({
        'userId': user_id,
        'groupName': group_name,
        'action': 'add'
    }))

    return func.HttpResponse(f"User {user_id} added to group {group_name}", status_code=200)


@app.route(route="remove_from_group", methods=["POST"])
@app.generic_output_binding(
    arg_name="signalRGroupActions",
    type="signalR",
    hubName=HUB_NAME,
    connectionStringSetting="AzureSignalRConnectionString"
)
def remove_from_group(req: func.HttpRequest, signalRGroupActions: func.Out[str]) -> func.HttpResponse:
    """
    Remove a user from a group.
    """
    try:
        body = req.get_json()
        user_id = body.get('userId')
        group_name = body.get('groupName')
    except (ValueError, json.JSONDecodeError) as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            status_code=400,
            mimetype="application/json"
        )

    if not user_id or not group_name:
        logging.error("Missing userId or groupName")
        return func.HttpResponse(
            json.dumps({"error": "userId and groupName required"}),
            status_code=400,
            mimetype="application/json"
        )

    logging.info(f"Removing user {user_id} from group {group_name}")

    signalRGroupActions.set(json.dumps({
        'userId': user_id,
        'groupName': group_name,
        'action': 'remove'
    }))

    return func.HttpResponse(f"User {user_id} removed from group {group_name}", status_code=200)


# =============================================================================
# SignalR Triggers (Connection and Message Events)
# =============================================================================

@app.generic_trigger(
    arg_name="invocation",
    type="signalRTrigger",
    hubName=HUB_NAME,
    category="connections",
    event="connected",
    connectionStringSetting="AzureSignalRConnectionString"
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/signalr-connected.txt",
    connection="AzureWebJobsStorage"
)
def on_connected(invocation: str) -> str:
    """
    Trigger fired when a client connects to the SignalR hub.
    Writes the connection info to blob storage for test verification.
    """
    logging.info(f"Client connected: {invocation}")

    try:
        ctx = json.loads(invocation)
        result = json.dumps({
            'event': 'connected',
            'connectionId': ctx.get('ConnectionId'),
            'userId': ctx.get('UserId'),
            'hub': ctx.get('Hub'),
            'category': ctx.get('Category'),
            'timestamp': ctx.get('Timestamp')
        })
    except (json.JSONDecodeError, TypeError):
        result = json.dumps({
            'event': 'connected',
            'raw': invocation
        })

    return result


@app.generic_trigger(
    arg_name="invocation",
    type="signalRTrigger",
    hubName=HUB_NAME,
    category="connections",
    event="disconnected",
    connectionStringSetting="AzureSignalRConnectionString"
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/signalr-disconnected.txt",
    connection="AzureWebJobsStorage"
)
def on_disconnected(invocation: str) -> str:
    """
    Trigger fired when a client disconnects from the SignalR hub.
    Writes the disconnection info to blob storage for test verification.
    """
    logging.info(f"Client disconnected: {invocation}")

    try:
        ctx = json.loads(invocation)
        result = json.dumps({
            'event': 'disconnected',
            'connectionId': ctx.get('ConnectionId'),
            'userId': ctx.get('UserId'),
            'error': ctx.get('Error'),
            'hub': ctx.get('Hub'),
            'category': ctx.get('Category')
        })
    except (json.JSONDecodeError, TypeError):
        result = json.dumps({
            'event': 'disconnected',
            'raw': invocation
        })

    return result


@app.generic_trigger(
    arg_name="invocation",
    type="signalRTrigger",
    hubName=HUB_NAME,
    category="messages",
    event="sendMessage",
    parameterNames='["message"]',
    connectionStringSetting="AzureSignalRConnectionString"
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/signalr-message.txt",
    connection="AzureWebJobsStorage"
)
def on_message(invocation: str) -> str:
    """
    Trigger fired when a client sends a 'sendMessage' to the hub.
    Writes the message info to blob storage for test verification.
    """
    logging.info(f"Message received: {invocation}")

    try:
        ctx = json.loads(invocation)
        result = json.dumps({
            'event': 'sendMessage',
            'connectionId': ctx.get('ConnectionId'),
            'userId': ctx.get('UserId'),
            'arguments': ctx.get('Arguments'),
            'hub': ctx.get('Hub'),
            'category': ctx.get('Category')
        })
    except (json.JSONDecodeError, TypeError):
        result = json.dumps({
            'event': 'sendMessage',
            'raw': invocation
        })

    return result


# =============================================================================
# Helper endpoints for test verification
# =============================================================================

@app.route(route="get_connected_event")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/signalr-connected.txt",
    connection="AzureWebJobsStorage"
)
def get_connected_event(req: func.HttpRequest, file: func.InputStream) -> func.HttpResponse:
    """
    Helper endpoint to retrieve the last connection event from blob storage.
    """
    if file:
        return func.HttpResponse(
            file.read().decode('utf-8'),
            status_code=200,
            mimetype='application/json'
        )
    return func.HttpResponse(
        json.dumps({"error": "No connection event found"}),
        status_code=404,
        mimetype='application/json'
    )


@app.route(route="get_disconnected_event")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/signalr-disconnected.txt",
    connection="AzureWebJobsStorage"
)
def get_disconnected_event(req: func.HttpRequest, file: func.InputStream) -> func.HttpResponse:
    """
    Helper endpoint to retrieve the last disconnection event from blob storage.
    """
    if file:
        return func.HttpResponse(
            file.read().decode('utf-8'),
            status_code=200,
            mimetype='application/json'
        )
    return func.HttpResponse(
        json.dumps({"error": "No disconnection event found"}),
        status_code=404,
        mimetype='application/json'
    )


@app.route(route="get_message_event")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/signalr-message.txt",
    connection="AzureWebJobsStorage"
)
def get_message_event(req: func.HttpRequest, file: func.InputStream) -> func.HttpResponse:
    """
    Helper endpoint to retrieve the last message event from blob storage.
    """
    if file:
        return func.HttpResponse(
            file.read().decode('utf-8'),
            status_code=200,
            mimetype='application/json'
        )
    return func.HttpResponse(
        json.dumps({"error": "No message event found"}),
        status_code=404,
        mimetype='application/json'
    )
