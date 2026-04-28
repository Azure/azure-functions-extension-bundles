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

@app.generic_trigger(
    arg_name="context",
    type="mcpPromptTrigger",
    promptName="greeting_prompt",
    description="Generates a greeting message for a given name.",
    promptArguments=json.dumps([
        {"name": "name", "description": "Name of the person to greet.", "required": True}
    ]),
)
def greeting_prompt(context) -> str:
    """
    A simple prompt function that returns a greeting message.

    Args:
        context: The prompt invocation context.

    Returns:
        str: A JSON-serialized prompt result with the greeting message.
    """
    ctx = json.loads(context)
    args = ctx.get("Arguments") or ctx.get("arguments") or {}
    name = args.get("name", "world")
    return json.dumps({
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": f"Say hello to {name}."}
            }
        ]
    })
