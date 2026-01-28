# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from requests import JSONDecodeError
from tests.utils import testutils
import logging


class TestMcpFunctions(testutils.WebHostTestCase):

    MCP_WEBHOOK_PATH = 'runtime/webhooks/mcp'

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'mcp_functions'

    def test_tools_list(self):
        """
        Test the tools/list MCP API to verify it returns available tools.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": "test-list-1",
            "method": "tools/list"
        }

        response = self.webhost.request(
            'POST',
            self.MCP_WEBHOOK_PATH,
            json=payload,
            no_prefix=True
        )

        self.assertEqual(response.status_code, 200)

        try:
            data = response.json()
            # Verify JSON-RPC response structure
            self.assertEqual(data.get("jsonrpc"), "2.0")
            self.assertEqual(data.get("id"), "test-list-1")
            self.assertIn("result", data)
            
            # Verify tools are returned
            result = data["result"]
            self.assertIn("tools", result)
            tools = result["tools"]
            self.assertIsInstance(tools, list)
            
            # Verify hello_mcp tool is in the list
            tool_names = [tool.get("name") for tool in tools]
            self.assertIn("hello_mcp", tool_names)
            
            # Verify hello_mcp tool has expected properties
            hello_mcp_tool = next(t for t in tools if t.get("name") == "hello_mcp")
            self.assertEqual(hello_mcp_tool.get("description"), "Hello world.")
        except JSONDecodeError:
            self.fail(f"Response is not valid JSON: {response.text}")

    def test_tools_call(self):
        """
        Test the tools/call MCP API to invoke the hello_mcp tool.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": "test-call-1",
            "method": "tools/call",
            "params": {
                "name": "hello_mcp",
                "arguments": {}
            }
        }

        response = self.webhost.request(
            'POST',
            self.MCP_WEBHOOK_PATH,
            json=payload,
            no_prefix=True
        )

        self.assertEqual(response.status_code, 200)

        try:
            data = response.json()
            # Verify JSON-RPC response structure
            self.assertEqual(data.get("jsonrpc"), "2.0")
            self.assertEqual(data.get("id"), "test-call-1")
            self.assertIn("result", data)
            
            # Verify the tool execution result
            result = data["result"]
            self.assertIn("content", result)
            content = result["content"]
            self.assertIsInstance(content, list)
            self.assertTrue(len(content) > 0)
            
            # Verify the text content from hello_mcp
            text_content = next((c for c in content if c.get("type") == "text"), None)
            self.assertIsNotNone(text_content, "Expected text content in response")
            self.assertEqual(text_content.get("text"), "Hello I am MCPTool!")
        except JSONDecodeError:
            self.fail(f"Response is not valid JSON: {response.text}")
