# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for wait_for_server and _start_mock_server in test_setup.py.

Tests the polling-based server readiness check that replaces
the flaky sleep-based wait pattern in CI, and the mock server
port retry logic.
"""

import errno
import threading
import time
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch

# Add parent directory to path so we can import test_setup
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from test_setup import wait_for_server, _start_mock_server


class _OKHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that always returns 200."""
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # Suppress log output during tests


class _DelayedStartHandler(BaseHTTPRequestHandler):
    """HTTP handler that starts returning 200 after a delay.
    
    Uses a class-level flag to control when to start responding.
    """
    ready = False

    def do_GET(self):
        if self.__class__.ready:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Not Ready")

    def log_message(self, format, *args):
        pass


class TestWaitForServer(unittest.TestCase):
    """Tests for the wait_for_server function."""

    def test_wait_for_server_success(self):
        """Server is already running -> should return True immediately."""
        server = HTTPServer(("127.0.0.1", 0), _OKHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            result = wait_for_server(
                f"http://127.0.0.1:{port}",
                timeout=5,
                interval=0.2,
            )
            self.assertTrue(result)
        finally:
            server.shutdown()
            server.server_close()

    def test_wait_for_server_delayed_start(self):
        """Server starts responding after a few retries -> should succeed."""
        _DelayedStartHandler.ready = False
        server = HTTPServer(("127.0.0.1", 0), _DelayedStartHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def make_ready():
            time.sleep(1.0)
            _DelayedStartHandler.ready = True

        ready_thread = threading.Thread(target=make_ready, daemon=True)
        ready_thread.start()

        try:
            result = wait_for_server(
                f"http://127.0.0.1:{port}",
                timeout=10,
                interval=0.3,
            )
            self.assertTrue(result)
        finally:
            _DelayedStartHandler.ready = False
            server.shutdown()
            server.server_close()

    def test_wait_for_server_timeout(self):
        """No server listening -> should raise TimeoutError after timeout."""
        # Use a port that is not listening
        with self.assertRaises(TimeoutError):
            wait_for_server(
                "http://127.0.0.1:19876",
                timeout=2,
                interval=0.3,
            )

    def test_wait_for_server_returns_false_on_503(self):
        """Server returns 503 until timeout -> should raise TimeoutError."""
        _DelayedStartHandler.ready = False
        server = HTTPServer(("127.0.0.1", 0), _DelayedStartHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with self.assertRaises(TimeoutError):
                wait_for_server(
                    f"http://127.0.0.1:{port}",
                    timeout=2,
                    interval=0.3,
                )
        finally:
            _DelayedStartHandler.ready = False
            server.shutdown()
            server.server_close()

    def test_wait_for_server_default_timeout(self):
        """Default timeout should be generous (>=60s)."""
        # We just verify the function signature accepts defaults
        # by calling with a running server and no explicit timeout
        server = HTTPServer(("127.0.0.1", 0), _OKHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            result = wait_for_server(f"http://127.0.0.1:{port}")
            self.assertTrue(result)
        finally:
            server.shutdown()
            server.server_close()

    def test_wait_for_server_survives_unexpected_exceptions(self):
        """Polling should not crash on unexpected exceptions (e.g. RemoteDisconnected).

        Simulates a scenario where urlopen raises an exception that is NOT
        URLError, HTTPError, or OSError.  The polling loop must keep going
        until timeout.
        """
        side_effects = [
            # First 3 calls raise an unusual exception
            Exception("Simulated RemoteDisconnected"),
            Exception("Simulated IncompleteRead"),
            Exception("Simulated BadStatusLine"),
        ]

        original_urlopen = __import__("urllib.request", fromlist=["urlopen"]).urlopen

        call_count = 0

        def patched_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= len(side_effects):
                raise side_effects[call_count - 1]
            # After the side_effects are exhausted, call real urlopen
            return original_urlopen(req, **kwargs)

        server = HTTPServer(("127.0.0.1", 0), _OKHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with patch("urllib.request.urlopen", side_effect=patched_urlopen):
                result = wait_for_server(
                    f"http://127.0.0.1:{port}",
                    timeout=10,
                    interval=0.2,
                )
            self.assertTrue(result)
            self.assertGreater(call_count, len(side_effects))
        finally:
            server.shutdown()
            server.server_close()


class TestStartMockServer(unittest.TestCase):
    """Tests for _start_mock_server port retry logic."""

    def test_start_mock_server_retries_on_port_conflict(self):
        """If port is already in use, should retry on port+1."""
        import tempfile
        import socket

        # Create a minimal temp dir structure
        temp_dir = pathlib.Path(tempfile.mkdtemp())
        try:
            # Pick a free port and then occupy it with a raw socket
            # so _start_mock_server sees EADDRINUSE
            blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            blocker.bind(("localhost", 0))
            blocker.listen(1)
            occupied_port = blocker.getsockname()[1]

            # _start_mock_server should get EADDRINUSE and retry on port+1
            server, server_thread = _start_mock_server(temp_dir, occupied_port)
            self.assertIsNotNone(server)
            # Server should be on the next port
            self.assertEqual(server.server_address[1], occupied_port + 1)

            server.shutdown()
            server.server_close()
            blocker.close()
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
