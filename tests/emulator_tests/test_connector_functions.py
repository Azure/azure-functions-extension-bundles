# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Bundle-level Connector Webhook delivery and request validation."""

import json
import uuid

from tests.utils import testutils


class TestConnectorFunctions(testutils.WebHostTestCase):
    CONNECTOR_WEBHOOK_PATH = 'runtime/webhooks/connector'

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'connector_functions'

    def _assert_post_delivery(self, function_name, result_route):
        payload = {
            'id': str(uuid.uuid4()),
            'metadata': {'source': 'office365'},
            'body': {
                'value': [{
                    'id': 'synthetic-message-001',
                    'subject': 'Connector callback \u65e5\u672c\u8a9e',
                    'from': 'sender@example.invalid',
                    'to': ['recipient@example.invalid'],
                }],
            },
        }
        response = self.webhost.request(
            'POST',
            f'{self.CONNECTOR_WEBHOOK_PATH}?functionName={function_name}',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            no_prefix=True, timeout=30)
        self.assertEqual(response.status_code, 202)
        result = self.webhost.request('GET', result_route, timeout=30)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), payload)

    def test_connector_webhook_default_mode_delivers_callback(self):
        self._assert_post_delivery(
            'connector_trigger_default', 'get_connector_default')

    def test_connector_webhook_explicit_mode_delivers_callback(self):
        self._assert_post_delivery(
            'connector_trigger_explicit', 'get_connector_explicit')

    def test_connector_webhook_rejects_invalid_requests(self):
        cases = [
            ('malformed_json', 'connector_trigger_default',
             '{"unfinished":', {'Content-Type': 'application/json'}, 400),
            ('unsupported_content_type', 'connector_trigger_default',
             'not-json', {'Content-Type': 'text/plain'}, 415),
            ('missing_function_name', None,
             '{}', {'Content-Type': 'application/json'}, 400),
            ('unknown_function', 'nonexistent_function',
             '{}', {'Content-Type': 'application/json'}, 404),
        ]
        for name, function_name, body, headers, expected in cases:
            with self.subTest(case=name):
                path = self.CONNECTOR_WEBHOOK_PATH
                if function_name is not None:
                    path += f'?functionName={function_name}'
                response = self.webhost.request(
                    'POST', path, data=body, headers=headers,
                    no_prefix=True, timeout=30)
                self.assertEqual(response.status_code, expected)
