# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from tests.utils import testutils
import logging


class TestMcpFunctions(testutils.WebHostTestCase):

    MCP_WEBHOOK_PATH = 'runtime/webhooks/mcp'

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'mcp_functions'

    def _parse_sse_response(self, response_text):
        """
        Parse Server-Sent Events (SSE) response and extract JSON data.
        SSE format: 
            event: message
            data: {"jsonrpc": "2.0", ...}
        """
        data_lines = []
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                # Extract the JSON data after 'data:'
                json_str = line[5:].strip()
                if json_str:
                    data_lines.append(json_str)
        
        if not data_lines:
            raise ValueError(f"No data found in SSE response: {response_text}")
        
        # Parse the last data line (the final response)
        return json.loads(data_lines[-1])

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
            # Try parsing as JSON first, then fall back to SSE
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = self._parse_sse_response(response.text)
            
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
        except (json.JSONDecodeError, ValueError) as e:
            self.fail(f"Failed to parse response: {e}\nResponse text: {response.text}")

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
            # Try parsing as JSON first, then fall back to SSE
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = self._parse_sse_response(response.text)
            
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
        except (json.JSONDecodeError, ValueError) as e:
            self.fail(f"Failed to parse response: {e}\nResponse text: {response.text}")
