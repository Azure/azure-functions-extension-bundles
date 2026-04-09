import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"

@app.generic_trigger(
    arg_name="context",
    type="mcpResourceTrigger",
    uri="file://readme.md",
    resourceName="readme",
    description="Application readme file",
    mimeType="text/plain",
)
def mcp_resource_function(context) -> str:
    """
    A simple function that returns a readme file content.

    Args:
        context: The resource invocation context.

    Returns:
        str: The readme content.
    """
    return "# Sample Readme\nThis is a sample readme file for testing MCP Resource Trigger."
