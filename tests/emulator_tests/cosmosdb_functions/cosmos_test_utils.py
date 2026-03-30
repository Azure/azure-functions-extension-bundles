# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Helper utilities for CosmosDB emulator tests.

Provides a DAO layer for directly interacting with CosmosDB
for test setup, verification, and cleanup.
"""
import os
import logging
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosResourceExistsError

logger = logging.getLogger(__name__)


class CosmosDBTestUtils:
    """Helper class for CosmosDB test operations"""

    def __init__(self, database_name: str = "test", container_name: str = "items"):
        self.url = os.getenv("CosmosDBEmulatorUrl")
        self.key = os.getenv("CosmosDBEmulatorKey")
        self.database_name = database_name
        self.container_name = container_name
        self.client = None
        self.database = None
        self.container = None

    def connect(self):
        """Connect to CosmosDB emulator"""
        if not self.url or not self.key:
            raise ValueError("CosmosDBEmulatorUrl and CosmosDBEmulatorKey must be set")

        self.client = CosmosClient(self.url, self.key)

        # Get or create database
        try:
            self.database = self.client.create_database(id=self.database_name)
        except CosmosResourceExistsError:
            self.database = self.client.get_database_client(self.database_name)

        # Get or create container
        try:
            self.container = self.database.create_container(
                id=self.container_name,
                partition_key=PartitionKey(path="/id")
            )
        except CosmosResourceExistsError:
            self.container = self.database.get_container_client(self.container_name)

        logger.info(f"Connected to CosmosDB: {self.database_name}/{self.container_name}")

    def ensure_lease_container(self, lease_container_name: str = "leases"):
        """Ensure lease container exists for trigger tests"""
        try:
            self.database.create_container(
                id=lease_container_name,
                partition_key=PartitionKey(path="/id")
            )
            logger.info(f"Created lease container: {lease_container_name}")
        except CosmosResourceExistsError:
            logger.info(f"Lease container already exists: {lease_container_name}")

    def insert_document(self, doc: dict) -> dict:
        """Insert a document into the container"""
        result = self.container.create_item(body=doc)
        logger.info(f"Inserted document: {doc.get('id')}")
        return result

    def upsert_document(self, doc: dict) -> dict:
        """Upsert a document into the container"""
        result = self.container.upsert_item(body=doc)
        logger.info(f"Upserted document: {doc.get('id')}")
        return result

    def get_document_by_id(self, doc_id: str, partition_key: str = None):
        """Get a document by ID"""
        if partition_key is None:
            partition_key = doc_id
        try:
            return self.container.read_item(item=doc_id, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return None

    def query_documents(self, query: str, parameters: list = None) -> list:
        """Execute a SQL query and return results"""
        items = list(self.container.query_items(
            query=query,
            parameters=parameters or [],
            enable_cross_partition_query=True
        ))
        return items

    def delete_document(self, doc_id: str, partition_key: str = None):
        """Delete a document by ID"""
        if partition_key is None:
            partition_key = doc_id
        try:
            self.container.delete_item(item=doc_id, partition_key=partition_key)
            logger.info(f"Deleted document: {doc_id}")
        except CosmosResourceNotFoundError:
            logger.warning(f"Document not found for deletion: {doc_id}")

    def clear_container(self):
        """Delete all documents in the container"""
        items = list(self.container.read_all_items())
        for item in items:
            self.container.delete_item(item=item['id'], partition_key=item['id'])
        logger.info(f"Cleared {len(items)} documents from container")

    def get_all_documents(self) -> list:
        """Get all documents in the container"""
        return list(self.container.read_all_items())

    def count_documents(self) -> int:
        """Count documents in the container"""
        return len(list(self.container.read_all_items()))

    def insert_multiple_documents(self, docs: list) -> list:
        """Insert multiple documents"""
        results = []
        for doc in docs:
            results.append(self.insert_document(doc))
        return results


class TriggerTestContainer:
    """Helper for managing a separate container to track trigger invocations"""

    CONTAINER_NAME = "trigger_tracking"

    def __init__(self, database_name: str = "test"):
        self.url = os.getenv("CosmosDBEmulatorUrl")
        self.key = os.getenv("CosmosDBEmulatorKey")
        self.database_name = database_name
        self.client = None
        self.database = None
        self.container = None

    def connect(self):
        """Connect and ensure tracking container exists"""
        self.client = CosmosClient(self.url, self.key)
        self.database = self.client.get_database_client(self.database_name)

        try:
            self.container = self.database.create_container(
                id=self.CONTAINER_NAME,
                partition_key=PartitionKey(path="/id")
            )
        except CosmosResourceExistsError:
            self.container = self.database.get_container_client(self.CONTAINER_NAME)

    def record_trigger_invocation(self, trigger_name: str, doc_ids: list):
        """Record that a trigger was invoked"""
        import time
        record = {
            "id": f"trigger-{int(time.time() * 1000)}",
            "trigger_name": trigger_name,
            "doc_ids": doc_ids,
            "timestamp": time.time()
        }
        self.container.create_item(body=record)

    def get_trigger_invocations(self, trigger_name: str = None) -> list:
        """Get all trigger invocation records"""
        if trigger_name:
            query = "SELECT * FROM c WHERE c.trigger_name = @name ORDER BY c.timestamp DESC"
            return list(self.container.query_items(
                query=query,
                parameters=[{"name": "@name", "value": trigger_name}],
                enable_cross_partition_query=True
            ))
        return list(self.container.read_all_items())

    def clear_invocations(self):
        """Clear all trigger invocation records"""
        items = list(self.container.read_all_items())
        for item in items:
            self.container.delete_item(item=item['id'], partition_key=item['id'])
