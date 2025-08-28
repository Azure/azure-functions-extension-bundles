# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from mysql.connector import Error
import time
from requests import JSONDecodeError
from tests.utils import testutils
from tests.emulator_tests.mysql_functions.mysql_test_utils import PersonDAO

class TestMySqlFunctions(testutils.WebHostTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.person_dao = PersonDAO()


    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'mysql_functions'

    def setUp(self):
        try:
            self.person_dao.connect()
            self.person_dao.create_table()
        except Error as e:
            print(f"[ERROR] Error while setting up Mysql table: {e}")
            raise

    @testutils.retryable_test(3, 5)
    def test_mysql_trigger(self):
        """Test MySQL trigger functionality
        
        Test Scenario:
        1. Insert a new person into the database.
        2. Verify that the insert was successful.
        3. Azure Mysql trigger function is expected to fire and update the address column with string
            "Function Triggered".
        4. Check that the MySQL trigger has fired by verifying the address column's value.
        """
        # Insert data to trigger the MySQL trigger
        row_id = self.person_dao.insert_person('itaque', '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')
        
        # Verify the insert was successful
        self.assertIsNotNone(row_id)
        
        # fetch the inserted row to ensure it exists
        person = self.person_dao.get_person_by_id(row_id)
        self.assertIsNotNone(person)
        self.assertEqual(person[0], row_id)

        print(f"Inserted person: ID={person[0]}, Name={person[1]}, Address={person[2]}")

        # MySQL trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 3
        for try_no in range(max_retries):
            time.sleep(2)
            
            try:
                # Check that the trigger has fired
                # If the trigger function is fired, it will update the address column
                result = self.person_dao.get_person_by_id(row_id)
                self.assertEqual(result[2], "Function Triggered")
                
                break
            except (AssertionError, JSONDecodeError):
                if try_no == max_retries - 1:
                    raise

    def test_mysql_insert_connectivity(self):
        """Test MySQL self.connection and data insertion"""
        row_id = self.person_dao.insert_person('itaque', '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')
        result = self.person_dao.get_person_by_id(row_id)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], row_id)


if __name__ == "__main__":
    test_instance = TestMySqlFunctions()
    test_instance.setUp()
    test_instance.test_mysql_insert_connectivity()
    test_instance.test_mysql_trigger()
