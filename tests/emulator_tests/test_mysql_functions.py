# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import mysql.connector
from mysql.connector import Error
import time

from requests import JSONDecodeError
from tests.utils import testutils


class TestMySqlFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'mysql_functions'

    def connect_and_insert(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        connection = None
        cursor = None
        try:
            # Connection string details
            connection = mysql.connector.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                autocommit=True,
                consume_results=True
            )
            
            print('Conn host:', connection.server_host)
            print("Successfully connected to MySQL database")
            
            cursor = connection.cursor(buffered=True)
            
            # # Create table if it doesn't exist
            # create_table_query = """
            # CREATE TABLE `person` (
            #     `id` int NOT NULL AUTO_INCREMENT,
            #     `name` varchar(100) NOT NULL,
            #     `address` varchar(255) NOT NULL,
            #     PRIMARY KEY (`id`)
            #     ) ENGINE=InnoDB;
            # """
            # cursor.execute(create_table_query)
            # print("Table 'person' created or already exists")
            
            # alter_table_query = """
            # ALTER TABLE person
            # ADD az_func_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE 
            # CURRENT_TIMESTAMP;
            # """
            # cursor.execute(alter_table_query)
            # print("Table 'person' altered to add 'az_func_updated_at' column")

            # Insert data
            insert_query = "INSERT INTO `person` (`name`, `address`) VALUES (%s, %s)"
            insert_data = ('itaque', '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')
            
            cursor.execute(insert_query, insert_data)
            cursor.fetchall()  # Consume any results
            
            print(f"Record inserted successfully. Row ID: {cursor.lastrowid}")
            
            # Verify the insert
            cursor.execute("SELECT * FROM person WHERE name = 'itaque'")
            result = cursor.fetchone()
            if result:
                print(f"Inserted record: Name={result[0]}, Address={result[1]}")
                return result
                
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")
            raise
        
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
                print("MySQL connection is closed")

    def test_mysql_insert(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        """Test MySQL connection and data insertion"""
        result = self.connect_and_insert(host, port, database, user, password)
        result2 = self.webhost.request('POST', 'put_mysql_trigger')

        print('**** Result ****', result)

        print('**** Result 2****', result2)
        # Assertions to verify the test
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'itaque')
        self.assertEqual(result[2], '0022 Gladys Spring Suite 961\nNasirstad, WI 40333')


if __name__ == "__main__":
    test_instance = TestMySqlFunctions()
    test_instance.test_mysql_insert(host='ams-mysql8.mysql.database.azure.com', port=3306, database='ams', user='cloudsa', password='Yukoon900')
