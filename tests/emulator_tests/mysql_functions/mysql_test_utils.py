# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import mysql.connector
from mysql.connector import Error
import os


class MySqlTestHelper:
    """Helper class to manage MySQL connection and operations"""

    def __init__(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        """Initialize MySQL connection parameters"""

        # Get the individual connection parameters from environment variable
        # if the environment variable is not set, use the provided defaults
        connection_string = os.environ.get("MySqlConnectionString")
        self.connection = None

        print("[DEBUG] Connection String:", connection_string)

        # If connection string is provided, parse it; otherwise use defaults
        if connection_string:
            conn_args = {}
            try:
                for kv in connection_string.split(';'):
                    if '=' in kv:  # Ensure the key-value pair is valid
                        key, value = kv.split('=', 1)
                        conn_args[key.strip()] = value.strip()

                self.host = conn_args.get('Server', host)
                self.port = int(conn_args.get('Port', port))
                self.database = conn_args.get('Database', database)
                self.user = conn_args.get('UserID', user)
                self.password = conn_args.get('Password', password)

                print("[INFO] Using connection string parameters")
            except (ValueError, AttributeError) as e:
                print(f"[WARNING] Error parsing connection string: {e}. Using default parameters.")
                # Fall back to default parameters
                self.host = host
                self.port = port
                self.database = database
                self.user = user
                self.password = password
        else:
            print("[INFO] MySqlConnectionString environment variable not set. Using default parameters.")
            # Use provided default parameters
            self.host = host
            self.port = port
            self.database = database
            self.user = user
            self.password = password

    def connect(self):
        """Establish connection to MySQL database"""
        if self.connection is None or not self.connection.is_connected():
            try:
                self.connection = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    autocommit=True,
                    consume_results=True
                )
                print("[INFO] MySQL connection established")

            except mysql.connector.Error as err:
                print(f"[ERROR] Error establishing mysql connection: {err}")

        return self.connection

    def __del__(self):
        """Close the MySQL connection upon deletion of the instance"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("[INFO] MySQL connection closed")


class PersonDAO(MySqlTestHelper):
    """Data Access Object for Person table operations

       Schema:
        id INT NOT NULL AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        address VARCHAR(255) NOT NULL,
        last_updated TIMESTAMP - Default Value CURRENT_TIMESTAMP
    """

    def __init__(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        super().__init__(host, port, database, user, password)
        self.connect()

    def insert_person(self, name, address):
        """Insert a new person into the database"""
        try:
            self.connect()
            cursor = self.connection.cursor(buffered=True)
            insert_query = "INSERT INTO `person` (`name`, `address`) VALUES (%s, %s)"
            cursor.execute(insert_query, (name, address))
            return cursor.lastrowid
        except Error as e:
            print(f"[ERROR] Error inserting person: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_person_by_id(self, id):
        """Retrieve a person by primary key id"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT * FROM person WHERE id = %s"
            cursor.execute(select_query, (id,))
            return cursor.fetchone()
        except Error as e:
            print(f"[ERROR] Error retrieving person by id: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def update_address_column(self, id):
        self.connect()
        cursor = self.connection.cursor()
        update_query = "UPDATE person SET address = %s WHERE id = %s"
        cursor.execute(update_query, ("Function Triggered", id))

    def create_table(self):
        """Create the person table if it does not exist"""
        try:
            self.connect()
            cursor = self.connection.cursor()

            # Create table if it doesn't exist
            create_table_query = """
                CREATE TABLE IF NOT EXISTS `person` (
                    `id` int NOT NULL AUTO_INCREMENT,
                    `name` varchar(100) NOT NULL,
                    `address` varchar(255) NOT NULL,
                    PRIMARY KEY (`id`)
                    ) ENGINE=InnoDB;
                """
            cursor.execute(create_table_query)
            print("[INFO] Table 'person' created or already exists")

            # Check if column exists before attempting to add it
            check_column_query = """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_NAME = 'person'
                AND COLUMN_NAME = 'az_func_updated_at'
                AND TABLE_SCHEMA = DATABASE();
            """
            cursor.execute(check_column_query)
            column_exists = cursor.fetchone()[0] > 0

            if not column_exists:
                alter_table_query = """
                ALTER TABLE person
                ADD az_func_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE
                CURRENT_TIMESTAMP;
                """
                cursor.execute(alter_table_query)
                print("[INFO] Table 'person' altered to add 'az_func_updated_at' column")
            else:
                print("[INFO] Column 'az_func_updated_at' already exists in table 'person'")

        except Error as e:
            print(f"[ERROR] Error creating table `person`: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def drop_table(self):
        """Drop the person table if it exists"""
        try:
            self.connect()
            cursor = self.connection.cursor()

            drop_table_query = "DROP TABLE IF EXISTS person"
            cursor.execute(drop_table_query)
            print("[INFO] Table 'person' dropped")
        except Error as e:
            print(f"[ERROR] Error dropping table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()


class ProductDAO(MySqlTestHelper):
    """Data Access Object for Products table operations

       Schema:
        ProductId INT NOT NULL PRIMARY KEY,
        Name VARCHAR(100) NOT NULL,
        Cost INT NOT NULL
    """

    def __init__(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        super().__init__(host, port, database, user, password)
        self.connect()

    def create_table(self):
        """Create the Products table if it does not exist"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            create_table_query = """
                CREATE TABLE IF NOT EXISTS `Products` (
                    `ProductId` int NOT NULL,
                    `Name` varchar(100) NOT NULL,
                    `Cost` int NOT NULL,
                    PRIMARY KEY (`ProductId`)
                ) ENGINE=InnoDB;
            """
            cursor.execute(create_table_query)
            print("[INFO] Table 'Products' created or already exists")

            check_column_query = """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_NAME = 'Products'
                AND COLUMN_NAME = 'az_func_updated_at'
                AND TABLE_SCHEMA = DATABASE();
            """
            cursor.execute(check_column_query)
            column_exists = cursor.fetchone()[0] > 0

            if not column_exists:
                alter_table_query = """
                ALTER TABLE Products
                ADD az_func_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
                """
                cursor.execute(alter_table_query)
                print("[INFO] Table 'Products' altered to add 'az_func_updated_at' column")
            else:
                print("[INFO] Column 'az_func_updated_at' already exists in table 'Products'")

        except Error as e:
            print(f"[ERROR] Error creating table `Products`: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def insert_product(self, product_id, name, cost):
        """Insert a new product into the database"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor(buffered=True)
            insert_query = "INSERT INTO `Products` (`ProductId`, `Name`, `Cost`) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (product_id, name, cost))
            return product_id
        except Error as e:
            print(f"[ERROR] Error inserting product: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_product_by_id(self, product_id):
        """Retrieve a product by primary key ProductId"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products WHERE ProductId = %s"
            cursor.execute(select_query, (product_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"[ERROR] Error retrieving product by id: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_products_by_cost(self, cost):
        """Retrieve products by cost"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products WHERE Cost = %s"
            cursor.execute(select_query, (cost,))
            return cursor.fetchall()
        except Error as e:
            print(f"[ERROR] Error retrieving products by cost: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_all_products(self):
        """Retrieve all products"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products"
            cursor.execute(select_query)
            return cursor.fetchall()
        except Error as e:
            print(f"[ERROR] Error retrieving all products: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def delete_product(self, product_id):
        """Delete a product by ProductId"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM Products WHERE ProductId = %s"
            cursor.execute(delete_query, (product_id,))
        except Error as e:
            print(f"[ERROR] Error deleting product: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def clear_all_products(self):
        """Delete all products from the table"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM Products"
            cursor.execute(delete_query)
            print("[INFO] All products cleared from table")
        except Error as e:
            print(f"[ERROR] Error clearing products: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def drop_table(self):
        """Drop the Products table if it exists"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            drop_table_query = "DROP TABLE IF EXISTS Products"
            cursor.execute(drop_table_query)
            print("[INFO] Table 'Products' dropped")
        except Error as e:
            print(f"[ERROR] Error dropping table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()


class TriggerTrackingDAO(MySqlTestHelper):
    """Data Access Object for TriggerTracking table operations

       Schema:
        Id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ProductId INT,
        Operation VARCHAR(20),
        ProductName VARCHAR(100),
        ProductCost INT,
        RecordedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """

    def __init__(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        super().__init__(host, port, database, user, password)
        self.connect()

    def create_table(self):
        """Create the TriggerTracking table if it does not exist"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            create_table_query = """
                CREATE TABLE IF NOT EXISTS `TriggerTracking` (
                    `Id` int NOT NULL AUTO_INCREMENT,
                    `ProductId` int,
                    `Operation` varchar(20),
                    `ProductName` varchar(100),
                    `ProductCost` int,
                    `RecordedAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`Id`)
                ) ENGINE=InnoDB;
            """
            cursor.execute(create_table_query)
            print("[INFO] Table 'TriggerTracking' created or already exists")

        except Error as e:
            print(f"[ERROR] Error creating table `TriggerTracking`: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def insert_tracking_record(self, product_id, operation, product_name, product_cost):
        """Insert a tracking record"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor(buffered=True)
            insert_query = """
                INSERT INTO `TriggerTracking` (`ProductId`, `Operation`, `ProductName`, `ProductCost`)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (product_id, operation, product_name, product_cost))
            return cursor.lastrowid
        except Error as e:
            print(f"[ERROR] Error inserting tracking record: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_tracked_changes(self, product_id=None, operation=None):
        """Retrieve tracked changes with optional filters"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            query = ("SELECT Id, ProductId, Operation, ProductName, ProductCost, RecordedAt "
                     "FROM TriggerTracking WHERE 1=1")
            params = []

            if product_id is not None:
                query += " AND ProductId = %s"
                params.append(product_id)

            if operation is not None:
                query += " AND Operation = %s"
                params.append(operation)

            query += " ORDER BY RecordedAt DESC"

            cursor.execute(query, params)
            return cursor.fetchall()
        except Error as e:
            print(f"[ERROR] Error retrieving tracked changes: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def clear_tracked_changes(self):
        """Delete all tracked changes"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM TriggerTracking"
            cursor.execute(delete_query)
            print("[INFO] All tracked changes cleared")
        except Error as e:
            print(f"[ERROR] Error clearing tracked changes: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def drop_table(self):
        """Drop the TriggerTracking table if it exists"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            drop_table_query = "DROP TABLE IF EXISTS TriggerTracking"
            cursor.execute(drop_table_query)
            print("[INFO] Table 'TriggerTracking' dropped")
        except Error as e:
            print(f"[ERROR] Error dropping table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()


class ProductsWithIdentityDAO(MySqlTestHelper):
    """Data Access Object for ProductsWithIdentity table operations

    This table has an AUTO_INCREMENT primary key, testing identity column handling.

       Schema:
        ProductId INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Name VARCHAR(100),
        Cost INT
    """

    def __init__(self, host='localhost', port=3307, database='testdb', user='user', password='password'):
        super().__init__(host, port, database, user, password)
        self.connect()

    def create_table(self):
        """Create the ProductsWithIdentity table if it does not exist"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            create_table_query = """
                CREATE TABLE IF NOT EXISTS `ProductsWithIdentity` (
                    `ProductId` int NOT NULL AUTO_INCREMENT,
                    `Name` varchar(100),
                    `Cost` int,
                    PRIMARY KEY (`ProductId`)
                ) ENGINE=InnoDB;
            """
            cursor.execute(create_table_query)
            print("[INFO] Table 'ProductsWithIdentity' created or already exists")

        except Error as e:
            print(f"[ERROR] Error creating table `ProductsWithIdentity`: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def insert_product(self, name, cost):
        """Insert a product without specifying ProductId (auto-generated)"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor(buffered=True)
            insert_query = "INSERT INTO `ProductsWithIdentity` (`Name`, `Cost`) VALUES (%s, %s)"
            cursor.execute(insert_query, (name, cost))
            return cursor.lastrowid
        except Error as e:
            print(f"[ERROR] Error inserting product: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_product_by_id(self, product_id):
        """Retrieve a product by primary key ProductId"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM ProductsWithIdentity WHERE ProductId = %s"
            cursor.execute(select_query, (product_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"[ERROR] Error retrieving product by id: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_all_products(self):
        """Retrieve all products"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM ProductsWithIdentity ORDER BY ProductId"
            cursor.execute(select_query)
            return cursor.fetchall()
        except Error as e:
            print(f"[ERROR] Error retrieving all products: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def clear_all_products(self):
        """Delete all products from the table"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM ProductsWithIdentity"
            cursor.execute(delete_query)
            cursor.execute("ALTER TABLE ProductsWithIdentity AUTO_INCREMENT = 1")
            print("[INFO] All products cleared from ProductsWithIdentity table")
        except Error as e:
            print(f"[ERROR] Error clearing products: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def drop_table(self):
        """Drop the ProductsWithIdentity table if it exists"""
        cursor = None
        try:
            self.connect()
            cursor = self.connection.cursor()

            drop_table_query = "DROP TABLE IF EXISTS ProductsWithIdentity"
            cursor.execute(drop_table_query)
            print("[INFO] Table 'ProductsWithIdentity' dropped")
        except Error as e:
            print(f"[ERROR] Error dropping table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
