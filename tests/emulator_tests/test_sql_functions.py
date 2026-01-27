# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Emulator tests for Azure Functions SQL Extension.

These tests validate SQL input bindings, output bindings, and trigger bindings
using a SQL Server emulator (e.g., SQL Server in Docker).

Test Requirements:
- SQL Server must be running and accessible
- SqlConnectionString environment variable must be set
- pyodbc and ODBC Driver 18 for SQL Server must be installed

Inspired by: https://github.com/Azure/azure-functions-sql-extension/tree/main/test/Integration/test-python
"""
import json
import logging
import time

from pyodbc import Error
from tests.utils import testutils
from tests.emulator_tests.sql_functions.sql_test_utils import (
    ProductDAO,
    TriggerTrackingDAO,
)

logger = logging.getLogger(__name__)


class TestSqlFunctions(testutils.WebHostTestCase):
    """Test class for SQL extension emulator tests"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.product_dao = ProductDAO()
        self.trigger_tracking_dao = TriggerTrackingDAO()

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / "sql_functions"

    def setUp(self):
        """Set up test fixtures - create tables and clear data"""
        try:
            self.product_dao.connect()
            self.product_dao.create_table()
            self.product_dao.clear_all_products()

            self.trigger_tracking_dao.connect()
            self.trigger_tracking_dao.create_table()
            self.trigger_tracking_dao.clear_tracked_changes()
        except Error as e:
            logger.error(f"Error while setting up SQL tables: {e}")
            raise

    def tearDown(self):
        """Clean up after tests"""
        try:
            self.product_dao.clear_all_products()
            self.trigger_tracking_dao.clear_tracked_changes()
        except Error as e:
            logger.warning(f"Error during teardown: {e}")

    # ========================================================================
    # SQL Output Binding Tests
    # ========================================================================

    def test_sql_output_add_single_product(self):
        """Test SQL output binding - add a single product via HTTP endpoint

        Test Scenario:
        1. POST a product to the AddProduct endpoint
        2. Verify the product was inserted into the database
        """
        product = {"ProductId": 1, "Name": "Test Product", "Cost": 100}

        # Add product via HTTP endpoint (SQL output binding)
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )

        self.assertEqual(r.status_code, 201)
        response = r.json()
        self.assertEqual(response["ProductId"], product["ProductId"])
        self.assertEqual(response["Name"], product["Name"])
        self.assertEqual(response["Cost"], product["Cost"])

        # Verify product was inserted in the database
        db_product = self.product_dao.get_product_by_id(1)
        self.assertIsNotNone(db_product)
        self.assertEqual(db_product[0], 1)  # ProductId
        self.assertEqual(db_product[1], "Test Product")  # Name
        self.assertEqual(db_product[2], 100)  # Cost

    def test_sql_output_upsert_product(self):
        """Test SQL output binding - upsert (update existing product)

        Test Scenario:
        1. Insert a product
        2. Update the same product via AddProduct endpoint
        3. Verify the product was updated, not duplicated
        """
        # First, insert a product
        product1 = {"ProductId": 2, "Name": "Original Product", "Cost": 50}
        r1 = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product1),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r1.status_code, 201)

        # Update the same product
        product2 = {"ProductId": 2, "Name": "Updated Product", "Cost": 75}
        r2 = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product2),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r2.status_code, 201)

        # Verify only one product exists with updated values
        db_product = self.product_dao.get_product_by_id(2)
        self.assertIsNotNone(db_product)
        self.assertEqual(db_product[1], "Updated Product")
        self.assertEqual(db_product[2], 75)

        # Verify there's only one product with this ID
        all_products = self.product_dao.get_all_products()
        products_with_id_2 = [p for p in all_products if p[0] == 2]
        self.assertEqual(len(products_with_id_2), 1)

    def test_sql_output_add_multiple_products(self):
        """Test SQL output binding - add multiple products at once

        Test Scenario:
        1. POST multiple products to the AddProducts endpoint
        2. Verify all products were inserted into the database
        """
        products = [
            {"ProductId": 10, "Name": "Product 10", "Cost": 1000},
            {"ProductId": 11, "Name": "Product 11", "Cost": 1100},
            {"ProductId": 12, "Name": "Product 12", "Cost": 1200},
        ]

        r = self.webhost.request(
            "POST",
            "addproducts",
            data=json.dumps(products),
            max_retries=3,
            expected_status=201,
        )

        self.assertEqual(r.status_code, 201)

        # Verify all products were inserted
        for product in products:
            db_product = self.product_dao.get_product_by_id(product["ProductId"])
            self.assertIsNotNone(
                db_product, f"Product {product['ProductId']} not found"
            )
            self.assertEqual(db_product[1], product["Name"])
            self.assertEqual(db_product[2], product["Cost"])

    # ========================================================================
    # SQL Input Binding Tests
    # ========================================================================

    def test_sql_input_get_products_by_cost(self):
        """Test SQL input binding - get products by cost

        Test Scenario:
        1. Insert products with different costs
        2. Query products by cost via GetProducts endpoint
        3. Verify correct products are returned
        """
        # Insert test products directly to DB
        self.product_dao.insert_product(20, "Cheap Product 1", 100)
        self.product_dao.insert_product(21, "Cheap Product 2", 100)
        self.product_dao.insert_product(22, "Expensive Product", 500)

        # Query products with cost = 100
        r = self.webhost.request(
            "GET", "getproducts/100", max_retries=3, expected_status=200
        )

        self.assertEqual(r.status_code, 200)
        products = r.json()

        self.assertEqual(len(products), 2)
        product_ids = [p["ProductId"] for p in products]
        self.assertIn(20, product_ids)
        self.assertIn(21, product_ids)
        self.assertNotIn(22, product_ids)

    def test_sql_input_get_product_by_id(self):
        """Test SQL input binding - get a single product by ID

        Test Scenario:
        1. Insert a product
        2. Query the product by ID via GetProductById endpoint
        3. Verify the correct product is returned
        """
        # Insert test product
        self.product_dao.insert_product(30, "Specific Product", 300)

        # Query product by ID
        r = self.webhost.request(
            "GET", "getproduct/30", max_retries=3, expected_status=200
        )

        self.assertEqual(r.status_code, 200)
        product = r.json()

        self.assertEqual(product["ProductId"], 30)
        self.assertEqual(product["Name"], "Specific Product")
        self.assertEqual(product["Cost"], 300)

    def test_sql_input_get_nonexistent_product(self):
        """Test SQL input binding - get a product that doesn't exist

        Test Scenario:
        1. Query a product ID that doesn't exist
        2. Verify 404 is returned
        """
        r = self.webhost.request(
            "GET", "getproduct/99999", max_retries=3, expected_status=404
        )

        self.assertEqual(r.status_code, 404)

    def test_sql_input_get_empty_result(self):
        """Test SQL input binding - get products with cost that doesn't exist

        Test Scenario:
        1. Query products with a cost that no product has
        2. Verify empty array is returned
        """
        # Insert a product with different cost
        r = self.webhost.request(
            "GET", "getproducts/99999", max_retries=3, expected_status=200
        )

        self.assertEqual(r.status_code, 200)
        products = r.json()
        self.assertEqual(len(products), 0)

    # ========================================================================
    # SQL Trigger Binding Tests
    # ========================================================================

    @testutils.retryable_test(3, 5)
    def test_sql_trigger_insert(self):
        """Test SQL trigger - fires on INSERT operation

        Test Scenario:
        1. Insert a product using SQL output binding
        2. Verify the trigger function was invoked
        3. Verify the change was recorded in TriggerTracking table
        """
        product = {"ProductId": 50, "Name": "Trigger Test Product", "Cost": 500}

        # Clear any existing tracked changes
        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        # Add product (should fire trigger)
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        # Wait for trigger to process (SQL triggers have some delay)
        max_retries = 10
        tracked_changes = []

        for attempt in range(max_retries):
            time.sleep(2)

            r = self.webhost.request(
                "GET",
                "gettrackedchanges?productId=50",
                max_retries=2,
                expected_status=200,
            )

            if r.status_code == 200:
                tracked_changes = r.json()
                if len(tracked_changes) > 0:
                    break

            logger.info(f"Waiting for trigger (attempt {attempt + 1}/{max_retries})...")

        # Verify trigger was invoked and recorded the Insert operation
        self.assertGreater(len(tracked_changes), 0, "No trigger changes recorded")

        insert_changes = [c for c in tracked_changes if c["Operation"] == "Insert"]
        self.assertGreater(len(insert_changes), 0, "No Insert operation recorded")

        change = insert_changes[0]
        self.assertEqual(change["ProductId"], 50)
        self.assertEqual(change["ProductName"], "Trigger Test Product")
        self.assertEqual(change["ProductCost"], 500)

    @testutils.retryable_test(3, 5)
    def test_sql_trigger_update(self):
        """Test SQL trigger - fires on UPDATE operation

        Test Scenario:
        1. Insert a product
        2. Wait for insert trigger
        3. Update the product using SQL output binding (upsert)
        4. Verify the Update trigger was invoked
        """
        product_id = 51

        # Clear tracked changes
        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        # First insert the product
        product = {"ProductId": product_id, "Name": "Original Name", "Cost": 100}
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        # Wait for insert trigger to complete
        time.sleep(5)

        # Clear tracked changes to isolate update
        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        # Update the product (upsert with same ProductId)
        updated_product = {"ProductId": product_id, "Name": "Updated Name", "Cost": 200}
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(updated_product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        # Wait for update trigger
        max_retries = 10
        tracked_changes = []

        for attempt in range(max_retries):
            time.sleep(2)

            r = self.webhost.request(
                "GET",
                f"gettrackedchanges?productId={product_id}",
                max_retries=2,
                expected_status=200,
            )

            if r.status_code == 200:
                tracked_changes = r.json()
                update_changes = [
                    c for c in tracked_changes if c["Operation"] == "Update"
                ]
                if len(update_changes) > 0:
                    break

            logger.info(
                f"Waiting for update trigger (attempt {attempt + 1}/{max_retries})..."
            )

        # Verify update trigger was invoked
        update_changes = [c for c in tracked_changes if c["Operation"] == "Update"]
        self.assertGreater(len(update_changes), 0, "No Update operation recorded")

        change = update_changes[0]
        self.assertEqual(change["ProductId"], product_id)
        self.assertEqual(change["ProductName"], "Updated Name")
        self.assertEqual(change["ProductCost"], 200)

    @testutils.retryable_test(3, 5)
    def test_sql_trigger_delete(self):
        """Test SQL trigger - fires on DELETE operation

        Test Scenario:
        1. Insert a product directly to DB
        2. Wait for insert trigger
        3. Delete the product directly from DB
        4. Verify the Delete trigger was invoked
        """
        product_id = 52

        # Insert product directly to DB
        self.product_dao.insert_product(product_id, "Product To Delete", 150)

        # Wait for insert trigger to complete
        time.sleep(5)

        # Clear tracked changes to isolate delete
        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        # Delete the product directly from DB
        self.product_dao.delete_product(product_id)

        # Wait for delete trigger
        max_retries = 10
        tracked_changes = []

        for attempt in range(max_retries):
            time.sleep(2)

            r = self.webhost.request(
                "GET",
                f"gettrackedchanges?productId={product_id}",
                max_retries=2,
                expected_status=200,
            )

            if r.status_code == 200:
                tracked_changes = r.json()
                delete_changes = [
                    c for c in tracked_changes if c["Operation"] == "Delete"
                ]
                if len(delete_changes) > 0:
                    break

            logger.info(
                f"Waiting for delete trigger (attempt {attempt + 1}/{max_retries})..."
            )

        # Verify delete trigger was invoked
        delete_changes = [c for c in tracked_changes if c["Operation"] == "Delete"]
        self.assertGreater(len(delete_changes), 0, "No Delete operation recorded")

        change = delete_changes[0]
        self.assertEqual(change["ProductId"], product_id)

    # ========================================================================
    # End-to-End Tests
    # ========================================================================

    def test_end_to_end_flow(self):
        """Test complete end-to-end flow with input and output bindings

        Test Scenario:
        1. Add multiple products via output binding
        2. Query products via input binding
        3. Verify data consistency
        """
        # Add products
        products = [
            {"ProductId": 60, "Name": "E2E Product 1", "Cost": 100},
            {"ProductId": 61, "Name": "E2E Product 2", "Cost": 100},
            {"ProductId": 62, "Name": "E2E Product 3", "Cost": 200},
        ]

        r = self.webhost.request(
            "POST",
            "addproducts",
            data=json.dumps(products),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        # Query products with cost = 100
        r = self.webhost.request(
            "GET", "getproducts/100", max_retries=3, expected_status=200
        )
        self.assertEqual(r.status_code, 200)

        result = r.json()
        result_ids = [p["ProductId"] for p in result]

        self.assertIn(60, result_ids)
        self.assertIn(61, result_ids)
        self.assertNotIn(62, result_ids)

        # Query single product
        r = self.webhost.request(
            "GET", "getproduct/62", max_retries=3, expected_status=200
        )
        self.assertEqual(r.status_code, 200)

        product = r.json()
        self.assertEqual(product["ProductId"], 62)
        self.assertEqual(product["Name"], "E2E Product 3")
        self.assertEqual(product["Cost"], 200)


if __name__ == "__main__":
    import unittest

    unittest.main()
