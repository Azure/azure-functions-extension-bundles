-- SQL Server initialization script for Azure Functions SQL extension tests
-- This script creates the necessary database and tables for testing

-- Create testdb database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'testdb')
BEGIN
    CREATE DATABASE testdb;
END
GO

USE testdb;
GO

-- Create Products table for SQL binding tests
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
BEGIN
    CREATE TABLE Products (
        ProductId INT PRIMARY KEY,
        Name NVARCHAR(100) NOT NULL,
        Cost INT NOT NULL
    );
END
GO

-- Enable change tracking on the database (required for SQL trigger)
IF NOT EXISTS (SELECT 1 FROM sys.change_tracking_databases WHERE database_id = DB_ID('testdb'))
BEGIN
    ALTER DATABASE testdb SET CHANGE_TRACKING = ON 
    (CHANGE_RETENTION = 2 DAYS, AUTO_CLEANUP = ON);
END
GO

-- Enable change tracking on Products table
IF NOT EXISTS (SELECT 1 FROM sys.change_tracking_tables WHERE object_id = OBJECT_ID('dbo.Products'))
BEGIN
    ALTER TABLE dbo.Products ENABLE CHANGE_TRACKING;
END
GO

-- Create TriggerTracking table for verifying trigger invocations
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
GO

PRINT 'SQL Server initialization complete for Azure Functions SQL extension tests';
GO
