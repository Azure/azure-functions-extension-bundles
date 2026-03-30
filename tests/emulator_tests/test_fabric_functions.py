# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from requests import JSONDecodeError
from tests.utils import testutils
import logging


class TestFabricFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'fabric_functions'

    def test_fabric_hello_world(self):
        """
        Test the test_hello_fabric function in the Fabric Functions extension.
        """

        response = self.webhost.request('POST', 'test_hello_fabric', json={}, headers={ 'x-ms-invocation-id': 'test-invocation-id' })

        self.assertEqual(response.status_code, 200)
        
        try:
            data = response.json()
            self.assertIn("output", data)
            self.assertEqual(data["output"], "Welcome to Fabric Functions")
        except JSONDecodeError:
            self.fail("Response is not valid JSON")


    def test_add_parameters(self):
        """
        Test the test_add_parameters function in the Fabric Functions extension.

        This function takes two parameters: a string and a number, and returns a formatted string.
        It is used to verify that the function can correctly handle parameters passed in the request body.
        """

        response = self.webhost.request('POST', 'test_add_parameters', json={"stringParam": "test", "numParam": 123}, headers={ 'x-ms-invocation-id': 'test-invocation-id' })

        self.assertEqual(response.status_code, 200)

        try:
            data = response.json()
            self.assertIn("output", data)
            self.assertEqual(data["output"], "stringParam: test, numParam: 123")
        except JSONDecodeError:
            self.fail("Response is not valid JSON")

    def test_fabric_connection(self):
        """
        Test the test_add_connection function in the Fabric Functions extension.
        This function is used to test the connection to a mock SQL database endpoint.
        It verifies that the connection string is correctly injected into the function context from the fabric host extension.
        """

        headers = {
            'x-ms-invocation-id': 'test-invocation-id',
            'x-ms-fabric-connected-datasources-connections': "{\"mockConnection_SqlEndpoint\": {\"SqlEndpoint\": \"Server=tcp:mock.database.windows.net,1433;Initial Catalog=mockdb;\"}}"
        }

        response = self.webhost.request('POST', 'test_add_connection', json={}, headers=headers)

        self.assertEqual(response.status_code, 200)

        try:
            data = response.json()
            self.assertIn("output", data)
            self.assertIn("mockSqlDB", data["output"])

            endpointInfo = data["output"]["mockSqlDB"]
            self.assertEqual(endpointInfo["sqlendpoint"]['ConnectionString'], "Server=tcp:mock.database.windows.net,1433;Initial Catalog=mockdb;")
        except JSONDecodeError:
            self.fail("Response is not valid JSON")

    def test_fabric_context(self):
        """
        Test the test_add_fabriccontext function in the Fabric Functions extension.
        This function is used to test the injection of the function context into the function.
        It verifies that the context information is correctly passed to the function.
        """

        context = {
            'InvocationId': 'test-invocation-id',
            'ExecutingUser': {
                'Oid': 'test-user',
                'TenantId': 'test-tenant-id',
                'PreferredUsername': 'TestTester'
            }
        }

        headers = {
            'x-ms-invocation-id': 'test-invocation-id',
            'x-ms-fabric-userdatafunctioncontext': json.dumps(context)
        }

        response = self.webhost.request('POST', 'test_add_fabriccontext', json={}, headers=headers)

        self.assertEqual(response.status_code, 200)

        try:
            data = response.json()

            self.assertIn("output", data)

            self.assertIn("executingUser", data["output"])
            user = data["output"]["executingUser"]

            self.assertEqual(user["Oid"], "test-user")
            self.assertEqual(user["TenantId"], "test-tenant-id")
            self.assertEqual(user["PreferredUsername"], "TestTester")
        except JSONDecodeError:
            self.fail("Response is not valid JSON")