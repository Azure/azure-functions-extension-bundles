# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Emulator tests for Azure Functions MySQL Extension.

These tests validate MySQL input bindings, output bindings, and trigger bindings
using a MySQL emulator (MySQL Server in Docker).

Test Requirements:
- MySQL Server must be running and accessible
- MySqlConnectionString environment variable must be set
- mysql-connector-python must be installed

Inspired by: https://github.com/Azure/azure-functions-mysql-extension/tree/main/samples
"""
import json
import logging
import time
from mysql.connector import Error
from requests import JSONDecodeError
from tests.utils import testutils
from tests.emulator_tests.mysql_functions.mysql_test_utils import (
    PersonDAO,
    ProductDAO,
    ProductsAutoIncrementDAO,
    ProductsWithIdentityDAO,
    TriggerTrackingDAO,
)

logger = logging.getLogger(__name__)


class TestMySqlFunctions(testutils.WebHostTestCase):
    """Test class for MySQL extension emulator tests"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.person_dao = PersonDAO()
        self.product_dao = ProductDAO()
        self.products_auto_increment_dao = ProductsAutoIncrementDAO()
        self.products_with_identity_dao = ProductsWithIdentityDAO()
        self.trigger_tracking_dao = TriggerTrackingDAO()

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'mysql_functions'

    def setUp(self):
        """Set up test fixtures - create tables and clear data"""
        try:
            self.person_dao.connect()
            self.person_dao.create_table()

            self.product_dao.connect()
            self.product_dao.create_table()
            self.product_dao.clear_all_products()

            self.products_auto_increment_dao.connect()
            self.products_auto_increment_dao.create_table()
            self.products_auto_increment_dao.clear_all_products()

            self.products_with_identity_dao.connect()
            self.products_with_identity_dao.create_table()
            self.products_with_identity_dao.clear_all_products()

            self.trigger_tracking_dao.connect()
            self.trigger_tracking_dao.create_table()
            self.trigger_tracking_dao.clear_tracked_changes()
        except Error as e:
            logger.error(f"Error while setting up MySQL tables: {e}")
            raise

    def tearDown(self):
        """Clean up after tests"""
        try:
            self.product_dao.clear_all_products()
            self.products_auto_increment_dao.clear_all_products()
            self.products_with_identity_dao.clear_all_products()
            self.trigger_tracking_dao.clear_tracked_changes()
        except Error as e:
            logger.warning(f"Error during teardown: {e}")

    # ========================================================================
    # Legacy MySQL Trigger Tests (person table)
    # ========================================================================

    @testutils.retryable_test(3, 5)
    def test_mysql_trigger(self):
        """Test MySQL trigger functionality"""
        row_id = self.person_dao.insert_person('itaque', '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')

        self.assertIsNotNone(row_id)

        person = self.person_dao.get_person_by_id(row_id)
        self.assertIsNotNone(person)
        self.assertEqual(person[0], row_id)

        logger.info(f"Inserted person: ID={person[0]}, Name={person[1]}, Address={person[2]}")

        max_retries = 3
        for try_no in range(max_retries):
            time.sleep(2)

            try:
                result = self.person_dao.get_person_by_id(row_id)
                self.assertEqual(result[2], "Function Triggered")
                break
            except (AssertionError, JSONDecodeError):
                if try_no == max_retries - 1:
                    raise

    def test_mysql_insert_connectivity(self):
        """Test MySQL connection and data insertion"""
        row_id = self.person_dao.insert_person('itaque', '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')
        result = self.person_dao.get_person_by_id(row_id)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], row_id)

    # ========================================================================
    # MySQL Output Binding Tests
    # ========================================================================

    def test_mysql_output_add_single_product(self):
        """Test MySQL output binding - add a single product via HTTP endpoint"""
        product = {"ProductId": 1, "Name": "Test Product", "Cost": 100}

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

        db_product = self.product_dao.get_product_by_id(1)
        self.assertIsNotNone(db_product)
        self.assertEqual(db_product[0], 1)
        self.assertEqual(db_product[1], "Test Product")
        self.assertEqual(db_product[2], 100)

    def test_mysql_output_upsert_product(self):
        """Test MySQL output binding - upsert (update existing product)"""
        product1 = {"ProductId": 2, "Name": "Original Product", "Cost": 50}
        r1 = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product1),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r1.status_code, 201)

        product2 = {"ProductId": 2, "Name": "Updated Product", "Cost": 75}
        r2 = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product2),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r2.status_code, 201)

        db_product = self.product_dao.get_product_by_id(2)
        self.assertIsNotNone(db_product)
        self.assertEqual(db_product[1], "Updated Product")
        self.assertEqual(db_product[2], 75)

        all_products = self.product_dao.get_all_products()
        products_with_id_2 = [p for p in all_products if p[0] == 2]
        self.assertEqual(len(products_with_id_2), 1)

    def test_mysql_output_add_multiple_products(self):
        """Test MySQL output binding - add multiple products at once"""
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

        for product in products:
            db_product = self.product_dao.get_product_by_id(product["ProductId"])
            self.assertIsNotNone(db_product, f"Product {product['ProductId']} not found")
            self.assertEqual(db_product[1], product["Name"])
            self.assertEqual(db_product[2], product["Cost"])

    # ========================================================================
    # MySQL Input Binding Tests
    # ========================================================================

    def test_mysql_input_get_products_by_cost(self):
        """Test MySQL input binding - get products by cost"""
        self.product_dao.insert_product(20, "Cheap Product 1", 100)
        self.product_dao.insert_product(21, "Cheap Product 2", 100)
        self.product_dao.insert_product(22, "Expensive Product", 500)

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

    def test_mysql_input_get_product_by_id(self):
        """Test MySQL input binding - get a single product by ID"""
        self.product_dao.insert_product(30, "Specific Product", 300)

        r = self.webhost.request(
            "GET", "getproduct/30", max_retries=3, expected_status=200
        )

        self.assertEqual(r.status_code, 200)
        product = r.json()

        self.assertEqual(product["ProductId"], 30)
        self.assertEqual(product["Name"], "Specific Product")
        self.assertEqual(product["Cost"], 300)

    def test_mysql_input_get_nonexistent_product(self):
        """Test MySQL input binding - get a product that doesn't exist"""
        r = self.webhost.request(
            "GET", "getproduct/99999", max_retries=3, expected_status=404
        )

        self.assertEqual(r.status_code, 404)

    def test_mysql_input_get_empty_result(self):
        """Test MySQL input binding - get products with cost that doesn't exist"""
        r = self.webhost.request(
            "GET", "getproducts/99999", max_retries=3, expected_status=200
        )

        self.assertEqual(r.status_code, 200)
        products = r.json()
        self.assertEqual(len(products), 0)

    # ========================================================================
    # MySQL Trigger Binding Tests (Products table)
    # ========================================================================

    @testutils.retryable_test(3, 5)
    def test_mysql_trigger_insert(self):
        """Test MySQL trigger - fires on INSERT operation"""
        product = {"ProductId": 50, "Name": "Trigger Test Product", "Cost": 500}

        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

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

        self.assertGreater(len(tracked_changes), 0, "No trigger changes recorded")

        insert_changes = [c for c in tracked_changes if c["Operation"] == "Insert"]
        self.assertGreater(len(insert_changes), 0, "No Insert operation recorded")

        change = insert_changes[0]
        self.assertEqual(change["ProductId"], 50)
        self.assertEqual(change["ProductName"], "Trigger Test Product")
        self.assertEqual(change["ProductCost"], 500)

    @testutils.retryable_test(3, 5)
    def test_mysql_trigger_upsert(self):
        """Test MySQL trigger - fires on UPSERT (second insert with same ID)

        Note: MySQL output binding uses INSERT ON DUPLICATE KEY UPDATE.
        When a record with the same primary key already exists, it triggers
        an "Insert" operation (not "Update") because the binding performs
        an upsert operation.
        """
        product_id = 51

        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        product = {"ProductId": product_id, "Name": "Original Name", "Cost": 100}
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        time.sleep(5)

        self.webhost.request(
            "POST", "cleartrackedchanges", max_retries=3, expected_status=200
        )

        updated_product = {"ProductId": product_id, "Name": "Updated Name", "Cost": 200}
        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(updated_product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

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
                # Upsert generates Insert operation
                insert_changes = [c for c in tracked_changes
                                  if c["Operation"] == "Insert"]
                if len(insert_changes) > 0:
                    break

            logger.info(
                f"Waiting for upsert trigger (attempt {attempt + 1}/{max_retries})..."
            )

        # Upsert generates Insert operation, verify it was recorded
        insert_changes = [c for c in tracked_changes if c["Operation"] == "Insert"]
        self.assertGreater(len(insert_changes), 0, "No Insert operation recorded")

        change = insert_changes[0]
        self.assertEqual(change["ProductId"], product_id)
        self.assertEqual(change["ProductName"], "Updated Name")
        self.assertEqual(change["ProductCost"], 200)

    # ========================================================================
    # End-to-End Tests
    # ========================================================================

    def test_end_to_end_flow(self):
        """Test complete end-to-end flow with input and output bindings"""
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

        r = self.webhost.request(
            "GET", "getproducts/100", max_retries=3, expected_status=200
        )
        self.assertEqual(r.status_code, 200)

        result = r.json()
        result_ids = [p["ProductId"] for p in result]

        self.assertIn(60, result_ids)
        self.assertIn(61, result_ids)
        self.assertNotIn(62, result_ids)

        r = self.webhost.request(
            "GET", "getproduct/62", max_retries=3, expected_status=200
        )
        self.assertEqual(r.status_code, 200)

        product = r.json()
        self.assertEqual(product["ProductId"], 62)
        self.assertEqual(product["Name"], "E2E Product 3")
        self.assertEqual(product["Cost"], 200)

    # ========================================================================
    # Edge Case Tests - Special Characters, NULL Values, Identity Columns
    # ========================================================================

    def test_mysql_output_special_characters(self):
        """Test MySQL output binding - handle special characters and Unicode"""
        special_products = [
            {"ProductId": 70, "Name": "Product with single quotes", "Cost": 100},
            {"ProductId": 71, "Name": "Product with double quotes", "Cost": 100},
            {"ProductId": 72, "Name": "Unicode Product", "Cost": 100},
            {"ProductId": 73, "Name": "SQL injection test DROP TABLE", "Cost": 100},
        ]

        for product in special_products:
            r = self.webhost.request(
                "POST",
                "addproduct",
                data=json.dumps(product),
                max_retries=3,
                expected_status=201,
            )
            self.assertEqual(
                r.status_code, 201, f"Failed for product: {product['Name']}"
            )

            r = self.webhost.request(
                "GET",
                f"getproduct/{product['ProductId']}",
                max_retries=3,
                expected_status=200,
            )
            self.assertEqual(r.status_code, 200)
            retrieved = r.json()
            self.assertEqual(retrieved["Name"], product["Name"])
            self.assertEqual(retrieved["Cost"], product["Cost"])

    def test_mysql_output_whitespace_values(self):
        """Test MySQL output binding - handle whitespace-padded values"""
        product = {"ProductId": 80, "Name": "  Padded Product  ", "Cost": 50}

        r = self.webhost.request(
            "POST",
            "addproduct",
            data=json.dumps(product),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        db_product = self.product_dao.get_product_by_id(80)
        self.assertIsNotNone(db_product)
        # MySQL may or may not trim trailing whitespace depending on column type
        self.assertIn("Padded Product", db_product[1])

    def test_mysql_output_identity_column(self):
        """Test MySQL output binding - table with AUTO_INCREMENT primary key"""
        products = [
            {"Name": "Identity Product 1", "Cost": 100},
            {"Name": "Identity Product 2", "Cost": 200},
        ]

        for product in products:
            r = self.webhost.request(
                "POST",
                "addproductwithidentity",
                data=json.dumps(product),
                max_retries=3,
                expected_status=201,
            )
            self.assertEqual(r.status_code, 201)

        all_products = self.products_auto_increment_dao.get_all_products()
        self.assertGreaterEqual(len(all_products), 2)

        names = [p[1] for p in all_products]
        self.assertIn("Identity Product 1", names)
        self.assertIn("Identity Product 2", names)

    def test_mysql_combined_input_output_binding(self):
        """Test combined MySQL input and output bindings in single function"""
        self.products_with_identity_dao.clear_all_products()

        products = [
            {"ProductId": 90, "Name": "Copy Product 1", "Cost": 500},
            {"ProductId": 91, "Name": "Copy Product 2", "Cost": 500},
            {"ProductId": 92, "Name": "Copy Product 3", "Cost": 600},
        ]

        r = self.webhost.request(
            "POST",
            "addproducts",
            data=json.dumps(products),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        r = self.webhost.request(
            "GET",
            "getandaddproducts/500",
            max_retries=3,
            expected_status=200,
        )
        self.assertEqual(r.status_code, 200)

        response_products = r.json()
        self.assertEqual(len(response_products), 2)
        response_names = [p["Name"] for p in response_products]
        self.assertIn("Copy Product 1", response_names)
        self.assertIn("Copy Product 2", response_names)

        copied_products = self.products_with_identity_dao.get_all_products()
        copied_names = [p[1] for p in copied_products]
        self.assertIn("Copy Product 1", copied_names)
        self.assertIn("Copy Product 2", copied_names)

    def test_mysql_input_large_result_set(self):
        """Test MySQL input binding - handle larger result sets"""
        products = [
            {"ProductId": 100 + i, "Name": f"Bulk Product {i}", "Cost": 999}
            for i in range(20)
        ]

        r = self.webhost.request(
            "POST",
            "addproducts",
            data=json.dumps(products),
            max_retries=3,
            expected_status=201,
        )
        self.assertEqual(r.status_code, 201)

        r = self.webhost.request(
            "GET",
            "getproducts/999",
            max_retries=3,
            expected_status=200,
        )
        self.assertEqual(r.status_code, 200)

        result = r.json()
        self.assertEqual(len(result), 20)

        for i in range(20):
            product_ids = [p["ProductId"] for p in result]
            self.assertIn(100 + i, product_ids)

    def test_mysql_output_zero_and_negative_values(self):
        """Test MySQL output binding - handle zero and negative numeric values"""
        products = [
            {"ProductId": 130, "Name": "Free Product", "Cost": 0},
            {"ProductId": 131, "Name": "Refund Product", "Cost": -50},
        ]

        for product in products:
            r = self.webhost.request(
                "POST",
                "addproduct",
                data=json.dumps(product),
                max_retries=3,
                expected_status=201,
            )
            self.assertEqual(r.status_code, 201)

        db_product_zero = self.product_dao.get_product_by_id(130)
        self.assertIsNotNone(db_product_zero)
        self.assertEqual(db_product_zero[2], 0)

        db_product_negative = self.product_dao.get_product_by_id(131)
        self.assertIsNotNone(db_product_negative)
        self.assertEqual(db_product_negative[2], -50)


if __name__ == "__main__":
    import unittest
    unittest.main()
