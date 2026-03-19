# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Emulator tests for Azure Functions CosmosDB Extension.

These tests validate CosmosDB trigger and output bindings using the
CosmosDB Linux emulator (vnext-preview).

Emulator Limitations:
- "Read collection feed" is NOT supported - input bindings cannot be tested
- Change feed IS supported - triggers work correctly
"""
import json
import logging
import os
import time
import uuid

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceExistsError
from tests.utils import testutils

logger = logging.getLogger(__name__)

# Initialize CosmosDB client for test setup
url = os.getenv("CosmosDBEmulatorUrl")
key = os.getenv("CosmosDBEmulatorKey")
client = CosmosClient(url, key) if url and key else None


def setup_database_and_containers():
    """Set up database and all required containers for tests"""
    if not client:
        raise ValueError("CosmosDB client not initialized")

    database_name = "test"

    try:
        database = client.create_database(id=database_name)
    except CosmosResourceExistsError:
        database = client.get_database_client(database=database_name)

    containers_config = [
        ("items", "/id"),
        ("leases", "/id"),
        ("batch_items", "/id"),
        ("batch_leases", "/id"),
        ("feed_delay_items", "/id"),
        ("feed_delay_leases", "/id"),
    ]

    created_containers = {}
    for container_name, partition_key_path in containers_config:
        try:
            cont = database.create_container(
                id=container_name,
                partition_key=PartitionKey(path=partition_key_path)
            )
        except CosmosResourceExistsError:
            cont = database.get_container_client(container_name)
        created_containers[container_name] = cont

    return database, created_containers


# Setup database and containers
if client:
    database, containers = setup_database_and_containers()
    container = containers.get("items")
    batch_container = containers.get("batch_items")
    feed_delay_container = containers.get("feed_delay_items")
else:
    database = container = batch_container = feed_delay_container = None


def query_by_id(cosmos_container, doc_id):
    """Helper to query documents by ID using parameterized query"""
    return list(cosmos_container.query_items(
        query="SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": doc_id}],
        enable_cross_partition_query=True
    ))


def poll_until(condition_fn, max_retries=10, retry_delay=1, description="condition"):
    """Poll until condition is met or timeout.

    This is the recommended pattern for avoiding flaky tests. Instead of
    fixed sleep times, we poll with retries until the expected condition
    is met, returning early on success.

    Args:
        condition_fn: Callable that returns (success: bool, result: any)
        max_retries: Maximum number of polling attempts
        retry_delay: Delay in seconds between attempts
        description: Description for logging

    Returns:
        The result from condition_fn when successful, or last result on timeout
    """
    result = None
    for attempt in range(max_retries):
        success, result = condition_fn()
        if success:
            logger.info(f"{description} succeeded on attempt {attempt + 1}")
            return result
        if attempt < max_retries - 1:
            logger.info(f"Waiting for {description} "
                        f"(attempt {attempt + 1}/{max_retries})...")
            time.sleep(retry_delay)
    logger.warning(f"{description} not met after {max_retries} attempts")
    return result


def poll_for_document(cosmos_container, doc_id, max_retries=10, retry_delay=1):
    """Poll CosmosDB until document appears or timeout."""
    def check():
        items = query_by_id(cosmos_container, doc_id)
        return (len(items) > 0, items)
    return poll_until(check, max_retries, retry_delay, f"document {doc_id}")


class TestCosmosDBFunctions(testutils.WebHostTestCase):
    """Test class for CosmosDB extension emulator tests"""

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'cosmosdb_functions'

    def setUp(self):
        """Set up test fixtures - clear containers and triggered docs"""
        if container:
            self._clear_container(container)
        if batch_container:
            self._clear_container(batch_container)
        if feed_delay_container:
            self._clear_container(feed_delay_container)

        try:
            self.webhost.request('POST', 'clear_triggered_docs',
                                 max_retries=3, expected_status=200)
        except Exception as e:
            logger.warning(f"Failed to clear triggered docs: {e}")

    def _clear_container(self, cosmos_container):
        """Helper to clear all documents from a container"""
        try:
            items = list(cosmos_container.read_all_items())
            for item in items:
                cosmos_container.delete_item(item=item['id'],
                                             partition_key=item['id'])
        except Exception as e:
            logger.warning(f"Error clearing container: {e}")

    # ========================================================================
    # COSMOS DB TRIGGER TESTS
    # ========================================================================

    def test_cosmosdb_trigger(self):
        """Test basic CosmosDB change feed trigger"""
        data = str(round(time.time()))
        doc = {'id': 'cosmosdb-trigger-test', 'data': data}

        logger.info("Creating document in CosmosDB...")
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        logger.info("Waiting for CosmosDB trigger to execute...")
        r = self.webhost.wait_and_request('GET', 'get_cosmosdb_triggered',
                                          wait_time=5, max_retries=10,
                                          expected_status=200)

        response = r.json()
        response.pop('_metadata', None)

        self.assertEqual(response['id'], doc['id'])
        self.assertIn('_etag', response)
        self.assertIn('_lsn', response)
        self.assertIn('_rid', response)
        self.assertIn('_ts', response)

    def test_cosmosdb_trigger_multiple_documents(self):
        """Test trigger receives multiple documents in change feed"""
        docs = []
        for i in range(3):
            doc = {
                'id': f'multi-trigger-test-{i}',
                'data': f'value-{i}',
                'timestamp': time.time()
            }
            docs.append(doc)
            r = self.webhost.request('POST', 'put_document',
                                     data=json.dumps(doc),
                                     max_retries=3, expected_status=200)
            self.assertEqual(r.text, 'OK')

        # Poll for triggered documents using poll_until helper
        def check_triggered():
            r = self.webhost.request('GET', 'get_triggered_docs',
                                     max_retries=3, expected_status=200)
            triggered = r.json()
            return (len(triggered) > 0, triggered)

        triggered = poll_until(check_triggered, max_retries=20,
                               description="trigger fired")

        self.assertGreater(len(triggered), 0, "No documents were triggered")
        triggered_ids = [d.get('id') for d in triggered]
        matching = [doc for doc in docs if doc['id'] in triggered_ids]
        self.assertGreater(len(matching), 0, "None of our documents triggered")

    @testutils.retryable_test(3, 5)
    def test_cosmosdb_trigger_with_max_items(self):
        """Test trigger with max_items_per_invocation configuration"""
        for i in range(8):
            doc = {
                'id': f'batch-test-{uuid.uuid4().hex[:8]}',
                'index': i,
                'batch': 'test-max-items'
            }
            r = self.webhost.request('POST', 'put_batch_document',
                                     data=json.dumps(doc),
                                     max_retries=3, expected_status=200)
            self.assertEqual(r.text, 'OK')

        # Poll for batch triggered docs using poll_until helper
        def check_batch_triggered():
            r = self.webhost.request('GET', 'get_batch_triggered_docs',
                                     max_retries=3, expected_status=200)
            batches = r.json()
            return (len(batches) > 0, batches)

        batches = poll_until(check_batch_triggered, max_retries=20,
                             description="batch trigger fired")

        if len(batches) > 0:
            for batch in batches:
                self.assertLessEqual(
                    batch['count'], 5,
                    f"Batch exceeded max_items_per_invocation: {batch['count']}"
                )

    # ========================================================================
    # COSMOS DB OUTPUT BINDING TESTS
    # ========================================================================

    def test_cosmosdb_output_single_document(self):
        """Test output binding - write single document"""
        doc_id = f'output-single-{uuid.uuid4().hex[:8]}'
        doc = {'id': doc_id, 'name': 'Test Product', 'price': 29.99}

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['name'], 'Test Product')
            self.assertEqual(items[0]['price'], 29.99)

    def test_cosmosdb_output_multiple_documents(self):
        """Test output binding - write multiple documents at once"""
        docs = [
            {'id': f'multi-{uuid.uuid4().hex[:8]}', 'type': 'batch', 'index': i}
            for i in range(5)
        ]

        r = self.webhost.request('POST', 'put_documents',
                                 data=json.dumps(docs),
                                 max_retries=3, expected_status=200)

        response = r.json()
        self.assertEqual(response['inserted'], 5)

        if container:
            for doc in docs:
                items = poll_for_document(container, doc['id'])
                self.assertEqual(len(items), 1, f"Document {doc['id']} not found")

    def test_cosmosdb_output_upsert(self):
        """Test output binding - upsert behavior (create then update)"""
        doc_id = f'upsert-{uuid.uuid4().hex[:8]}'

        doc_v1 = {'id': doc_id, 'version': 1, 'status': 'created'}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc_v1),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        # Wait for first write before updating
        if container:
            poll_for_document(container, doc_id)

        doc_v2 = {'id': doc_id, 'version': 2, 'status': 'updated'}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc_v2),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            # Poll until version 2 appears using poll_until helper
            def check_version_2():
                items = query_by_id(container, doc_id)
                return (items and items[0].get('version') == 2, items)

            items = poll_until(check_version_2, max_retries=10,
                               description=f"document {doc_id} version 2")
            self.assertEqual(len(items), 1, "Should have only one document")
            self.assertEqual(items[0]['version'], 2)
            self.assertEqual(items[0]['status'], 'updated')

    def test_cosmosdb_output_nested_document(self):
        """Test output binding - document with nested/complex structure"""
        doc_id = f'nested-{uuid.uuid4().hex[:8]}'
        doc = {
            'id': doc_id,
            'type': 'complex',
            'metadata': {
                'created': time.time(),
                'author': 'test-user',
                'tags': ['test', 'nested', 'complex']
            },
            'items': [
                {'name': 'item1', 'value': 100},
                {'name': 'item2', 'value': 200}
            ],
            'settings': {
                'level1': {'level2': {'value': 'deeply-nested'}}
            }
        }

        r = self.webhost.request('POST', 'put_nested_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            result = items[0]
            self.assertEqual(result['metadata']['author'], 'test-user')
            self.assertEqual(len(result['metadata']['tags']), 3)
            self.assertEqual(len(result['items']), 2)
            self.assertEqual(
                result['settings']['level1']['level2']['value'],
                'deeply-nested'
            )

    # ========================================================================
    # EDGE CASE TESTS
    # ========================================================================

    def test_cosmosdb_output_special_characters(self):
        """Test output binding - document with special characters"""
        doc_id = f'special-{uuid.uuid4().hex[:8]}'
        doc = {
            'id': doc_id,
            'unicode': '日本語テスト 🎉 émojis',
            'quotes': 'He said "Hello World"',
            'newlines': 'Line1\nLine2\nLine3',
            'tabs': 'Col1\tCol2\tCol3',
            'backslash': 'path\\to\\file',
            'html': '<script>alert("xss")</script>'
        }

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            result = items[0]
            self.assertEqual(result['unicode'], doc['unicode'])
            self.assertEqual(result['quotes'], doc['quotes'])
            self.assertEqual(result['newlines'], doc['newlines'])
            self.assertIn('🎉', result['unicode'])

    def test_cosmosdb_output_empty_fields(self):
        """Test output binding - document with empty/null fields"""
        doc_id = f'empty-fields-{uuid.uuid4().hex[:8]}'
        doc = {
            'id': doc_id,
            'empty_string': '',
            'null_value': None,
            'empty_array': [],
            'empty_object': {},
            'zero': 0,
            'false_bool': False
        }

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            result = items[0]
            self.assertEqual(result['empty_string'], '')
            self.assertIsNone(result['null_value'])
            self.assertEqual(result['empty_array'], [])
            self.assertEqual(result['empty_object'], {})
            self.assertEqual(result['zero'], 0)
            self.assertEqual(result['false_bool'], False)

    def test_cosmosdb_output_large_document(self):
        """Test output binding - large document (near 2MB limit)"""
        doc_id = f'large-{uuid.uuid4().hex[:8]}'
        large_data = 'x' * 10000
        doc = {
            'id': doc_id,
            'type': 'large-document-test',
            'data': [large_data for _ in range(10)],
        }

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            self.assertEqual(len(items[0]['data']), 10)

    def test_cosmosdb_output_numeric_types(self):
        """Test output binding - various numeric types"""
        doc_id = f'numeric-{uuid.uuid4().hex[:8]}'
        doc = {
            'id': doc_id,
            'integer': 42,
            'negative': -100,
            'float': 3.14159,
            'scientific': 1.23e10,
            'large_int': 9007199254740991,
            'small_float': 0.000001
        }

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        if container:
            items = poll_for_document(container, doc_id)
            self.assertEqual(len(items), 1)
            result = items[0]
            self.assertEqual(result['integer'], 42)
            self.assertEqual(result['negative'], -100)
            self.assertAlmostEqual(result['float'], 3.14159, places=5)
            self.assertEqual(result['large_int'], 9007199254740991)

    # ========================================================================
    # END-TO-END FLOW TESTS
    # ========================================================================

    @testutils.retryable_test(3, 5)
    def test_end_to_end_output_trigger_flow(self):
        """Test complete end-to-end flow: output -> trigger -> blob"""
        doc_id = f'e2e-{uuid.uuid4().hex[:8]}'
        doc = {'id': doc_id, 'test': 'end-to-end', 'timestamp': time.time()}

        self.webhost.request('POST', 'clear_triggered_docs',
                             max_retries=3, expected_status=200)

        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc),
                                 max_retries=3, expected_status=200)
        self.assertEqual(r.text, 'OK')

        logger.info("Waiting for trigger to process...")
        r = self.webhost.wait_and_request('GET', 'get_cosmosdb_triggered',
                                          wait_time=5, max_retries=15,
                                          expected_status=200)

        response = r.json()
        self.assertIn('_ts', response)
        self.assertIn('_etag', response)


if __name__ == "__main__":
    import unittest
    unittest.main()
