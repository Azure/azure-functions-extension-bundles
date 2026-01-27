# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pyodbc
import os
import logging

logger = logging.getLogger(__name__)


class SqlTestHelper:
    """Helper class to manage SQL Server connection and operations"""
    
    def __init__(self, server='localhost', port=1433, database='testdb', 
                 user='sa', password='YourStrong@Passw0rd'):
        """Initialize SQL Server connection parameters"""
        
        # Get the connection string from environment variable
        connection_string = os.environ.get("SqlConnectionString")
        self.connection = None

        logger.debug(f"Connection String: {connection_string}")
        
        # If connection string is provided, use it directly; otherwise build from parameters
        if connection_string:
            self.connection_string = connection_string
            logger.info("Using SqlConnectionString environment variable")
        else:
            logger.info("SqlConnectionString environment variable not set. Using default parameters.")
            # Build connection string from parameters
            self.connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server={server},{port};"
                f"Database={database};"
                f"UID={user};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
            )

    def connect(self):
        """Establish connection to SQL Server database"""
        if self.connection is None:
            try:
                self.connection = pyodbc.connect(self.connection_string, autocommit=True)
                logger.info("SQL Server connection established")
            except pyodbc.Error as err:
                logger.error(f"Error establishing SQL Server connection: {err}")
                raise
        
        return self.connection

    def close(self):
        """Close the SQL Server connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("SQL Server connection closed")

    def __del__(self):
        """Close the SQL Server connection upon deletion of the instance"""
        self.close()


class ProductDAO(SqlTestHelper):
    """Data Access Object for Products table operations

       Schema:
        ProductId INT PRIMARY KEY,
        Name NVARCHAR(100) NOT NULL,
        Cost INT NOT NULL
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def create_table(self):
        """Create the Products table if it doesn't exist"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            
            # Create Products table
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
            BEGIN
                CREATE TABLE Products (
                    ProductId INT PRIMARY KEY,
                    Name NVARCHAR(100) NOT NULL,
                    Cost INT NOT NULL
                );
            END
            """
            cursor.execute(create_table_query)
            cursor.commit()
            logger.info("Products table created or already exists")
            
            # Enable change tracking for the Products table (required for SQL trigger)
            # First check if change tracking is enabled on the database
            enable_db_ct = """
            IF NOT EXISTS (SELECT 1 FROM sys.change_tracking_databases WHERE database_id = DB_ID())
            BEGIN
                ALTER DATABASE CURRENT SET CHANGE_TRACKING = ON 
                (CHANGE_RETENTION = 2 DAYS, AUTO_CLEANUP = ON);
            END
            """
            cursor.execute(enable_db_ct)
            cursor.commit()
            
            # Then enable change tracking on the table
            enable_table_ct = """
            IF NOT EXISTS (SELECT 1 FROM sys.change_tracking_tables WHERE object_id = OBJECT_ID('dbo.Products'))
            BEGIN
                ALTER TABLE dbo.Products ENABLE CHANGE_TRACKING;
            END
            """
            cursor.execute(enable_table_ct)
            cursor.commit()
            logger.info("Change tracking enabled for Products table")
            
        except pyodbc.Error as err:
            logger.error(f"Error creating Products table: {err}")
            raise

    def insert_product(self, product_id, name, cost):
        """Insert a new product into the database using MERGE (upsert)"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            
            # Use MERGE to handle both insert and update
            upsert_query = """
            MERGE dbo.Products AS target
            USING (SELECT ? AS ProductId, ? AS Name, ? AS Cost) AS source
            ON target.ProductId = source.ProductId
            WHEN MATCHED THEN
                UPDATE SET Name = source.Name, Cost = source.Cost
            WHEN NOT MATCHED THEN
                INSERT (ProductId, Name, Cost) VALUES (source.ProductId, source.Name, source.Cost);
            """
            cursor.execute(upsert_query, (product_id, name, cost))
            cursor.commit()
            logger.info(f"Product inserted/updated: ID={product_id}, Name={name}, Cost={cost}")
            return product_id
            
        except pyodbc.Error as err:
            logger.error(f"Error inserting product: {err}")
            raise

    def get_product_by_id(self, product_id):
        """Get a product by its ID"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products WHERE ProductId = ?"
            cursor.execute(select_query, (product_id,))
            result = cursor.fetchone()
            return result
            
        except pyodbc.Error as err:
            logger.error(f"Error getting product: {err}")
            raise

    def get_products_by_cost(self, cost):
        """Get products by cost"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products WHERE Cost = ?"
            cursor.execute(select_query, (cost,))
            results = cursor.fetchall()
            return results
            
        except pyodbc.Error as err:
            logger.error(f"Error getting products by cost: {err}")
            raise

    def update_product_name(self, product_id, new_name):
        """Update a product's name"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            update_query = "UPDATE Products SET Name = ? WHERE ProductId = ?"
            cursor.execute(update_query, (new_name, product_id))
            cursor.commit()
            logger.info(f"Product name updated: ID={product_id}, NewName={new_name}")
            
        except pyodbc.Error as err:
            logger.error(f"Error updating product: {err}")
            raise

    def delete_product(self, product_id):
        """Delete a product by its ID"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM Products WHERE ProductId = ?"
            cursor.execute(delete_query, (product_id,))
            cursor.commit()
            logger.info(f"Product deleted: ID={product_id}")
            
        except pyodbc.Error as err:
            logger.error(f"Error deleting product: {err}")
            raise

    def clear_all_products(self):
        """Delete all products from the table"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM Products"
            cursor.execute(delete_query)
            cursor.commit()
            logger.info("All products deleted")
            
        except pyodbc.Error as err:
            logger.error(f"Error clearing products: {err}")
            raise

    def get_all_products(self):
        """Get all products from the table"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            select_query = "SELECT ProductId, Name, Cost FROM Products ORDER BY ProductId"
            cursor.execute(select_query)
            results = cursor.fetchall()
            return results
            
        except pyodbc.Error as err:
            logger.error(f"Error getting all products: {err}")
            raise


class TriggerTrackingDAO(SqlTestHelper):
    """Data Access Object for tracking trigger invocations
    
    This table is used to verify that SQL triggers are being fired correctly.
    When a trigger function fires, it records the change in this table.
    
    Schema:
        Id INT IDENTITY(1,1) PRIMARY KEY,
        ProductId INT NOT NULL,
        Operation NVARCHAR(20) NOT NULL,  -- 'Insert', 'Update', 'Delete'
        ProductName NVARCHAR(100),
        ProductCost INT,
        RecordedAt DATETIME2 DEFAULT GETUTCDATE()
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def create_table(self):
        """Create the TriggerTracking table if it doesn't exist"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TriggerTracking')
            BEGIN
                CREATE TABLE TriggerTracking (
                    Id INT IDENTITY(1,1) PRIMARY KEY,
                    ProductId INT NOT NULL,
                    Operation NVARCHAR(20) NOT NULL,
                    ProductName NVARCHAR(100),
                    ProductCost INT,
                    RecordedAt DATETIME2 DEFAULT GETUTCDATE()
                );
            END
            """
            cursor.execute(create_table_query)
            cursor.commit()
            logger.info("TriggerTracking table created or already exists")
            
        except pyodbc.Error as err:
            logger.error(f"Error creating TriggerTracking table: {err}")
            raise

    def get_tracked_changes(self, product_id=None, operation=None):
        """Get tracked changes, optionally filtered by product_id and/or operation"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            
            query = "SELECT Id, ProductId, Operation, ProductName, ProductCost, RecordedAt FROM TriggerTracking WHERE 1=1"
            params = []
            
            if product_id is not None:
                query += " AND ProductId = ?"
                params.append(product_id)
            
            if operation is not None:
                query += " AND Operation = ?"
                params.append(operation)
            
            query += " ORDER BY RecordedAt DESC"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
            
        except pyodbc.Error as err:
            logger.error(f"Error getting tracked changes: {err}")
            raise

    def clear_tracked_changes(self):
        """Clear all tracked changes"""
        try:
            self.connect()
            cursor = self.connection.cursor()
            delete_query = "DELETE FROM TriggerTracking"
            cursor.execute(delete_query)
            cursor.commit()
            logger.info("All tracked changes cleared")
            
        except pyodbc.Error as err:
            logger.error(f"Error clearing tracked changes: {err}")
            raise
