# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
from typing import Optional
import azure.functions as func
import pyodbc
import os

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _convert_to_odbc(ado_connection_string: str) -> str:
    """Convert ADO.NET connection string to ODBC format for pyodbc.

    ADO.NET format: Server=localhost,1433;Database=testdb;User Id=sa;Password=xxx;TrustServerCertificate=True
    ODBC format: Driver={ODBC Driver 18 for SQL Server};Server=localhost,1433;Database=testdb;UID=sa;PWD=xxx;TrustServerCertificate=yes
    """
    # Parse the connection string
    params = {}
    for part in ado_connection_string.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.strip().lower()] = value.strip()

    # Map ADO.NET keys to ODBC keys
    server = params.get('server', 'localhost,1433')
    database = params.get('database', 'testdb')
    user = params.get('user id', params.get('uid', 'sa'))
    password = params.get('password', params.get('pwd', ''))
    trust_cert = params.get('trustservercertificate', 'True').lower() in ('true', 'yes', '1')

    # Build ODBC connection string
    odbc_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate={'yes' if trust_cert else 'no'};"
    )

    return odbc_string


def _get_odbc_connection_string() -> Optional[str]:
    """Get ODBC-formatted connection string from environment variable."""
    connection_string = os.environ.get("SqlConnectionString")
    if connection_string:
        return _convert_to_odbc(connection_string)
    return None


# ============================================================================
# SQL Input Binding - Get products by cost
# ============================================================================
@app.function_name(name="GetProducts")
@app.route(route="getproducts/{cost}")
@app.sql_input(arg_name="products",
               command_text="SELECT * FROM Products WHERE Cost = @Cost",
               command_type="Text",
               parameters="@Cost={cost}",
               connection_string_setting="SqlConnectionString")
def get_products(req: func.HttpRequest, products: func.SqlRowList) -> func.HttpResponse:
    """
    HTTP triggered function with SQL input binding.
    Returns products where Cost matches the specified value.
    """
    rows = list(map(lambda r: json.loads(r.to_json()), products))
    
    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )


# ============================================================================
# SQL Input Binding - Get product by ID
# ============================================================================
@app.function_name(name="GetProductById")
@app.route(route="getproduct/{id}")
@app.sql_input(arg_name="products",
               command_text="SELECT * FROM Products WHERE ProductId = @ProductId",
               command_type="Text",
               parameters="@ProductId={id}",
               connection_string_setting="SqlConnectionString")
def get_product_by_id(req: func.HttpRequest, products: func.SqlRowList) -> func.HttpResponse:
    """
    HTTP triggered function with SQL input binding.
    Returns a single product by ProductId.
    """
    rows = list(map(lambda r: json.loads(r.to_json()), products))
    
    if len(rows) == 0:
        return func.HttpResponse(
            json.dumps({"error": "Product not found"}),
            status_code=404,
            mimetype="application/json"
        )
    
    return func.HttpResponse(
        json.dumps(rows[0]),
        status_code=200,
        mimetype="application/json"
    )


# ============================================================================
# SQL Output Binding - Add/Upsert a single product
# ============================================================================
@app.function_name(name="AddProduct")
@app.route(route="addproduct")
@app.sql_output(arg_name="product",
                command_text="[dbo].[Products]",
                connection_string_setting="SqlConnectionString")
def add_product(req: func.HttpRequest, product: func.Out[func.SqlRow]) -> func.HttpResponse:
    """
    HTTP triggered function with SQL output binding.
    Upserts a product - inserts if ProductId doesn't exist, updates if it does.
    """
    try:
        body = json.loads(req.get_body())
        row = func.SqlRow.from_dict(body)
        product.set(row)
        
        return func.HttpResponse(
            body=req.get_body(),
            status_code=201,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error adding product: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )


# ============================================================================
# SQL Output Binding - Add multiple products
# ============================================================================
@app.function_name(name="AddProducts")
@app.route(route="addproducts")
@app.sql_output(arg_name="products",
                command_text="[dbo].[Products]",
                connection_string_setting="SqlConnectionString")
def add_products(req: func.HttpRequest, products: func.Out[func.SqlRowList]) -> func.HttpResponse:
    """
    HTTP triggered function with SQL output binding.
    Upserts multiple products at once.
    """
    try:
        body = json.loads(req.get_body())
        rows = func.SqlRowList(map(lambda r: func.SqlRow.from_dict(r), body))
        products.set(rows)
        
        return func.HttpResponse(
            body=req.get_body(),
            status_code=201,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error adding products: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )


# ============================================================================
# SQL Trigger Binding - React to changes in Products table
# ============================================================================
@app.function_name(name="ProductsTrigger")
@app.sql_trigger(arg_name="changes",
                 table_name="Products",
                 connection_string_setting="SqlConnectionString")
def products_trigger(changes: str) -> None:
    """
    SQL trigger function that fires when changes occur in the Products table.
    Records the changes to TriggerTracking table for verification.
    """
    logging.info(f"SQL Changes: {changes}")
    
    conn = None
    cursor = None
    try:
        # Parse the changes
        change_list = json.loads(changes)
        
        # Get ODBC-formatted connection string and record changes to tracking table
        odbc_connection_string = _get_odbc_connection_string()
        if odbc_connection_string:
            conn = pyodbc.connect(odbc_connection_string, autocommit=True)
            cursor = conn.cursor()
            
            for change in change_list:
                operation = change.get("Operation")  # 0=Insert, 1=Update, 2=Delete
                item = change.get("Item", {})
                product_id = item.get("ProductId")
                product_name = item.get("Name")
                product_cost = item.get("Cost")
                
                # Map operation code to string
                operation_map = {0: "Insert", 1: "Update", 2: "Delete"}
                operation_str = operation_map.get(operation, str(operation))
                
                # Insert record into tracking table
                insert_query = """
                INSERT INTO TriggerTracking (ProductId, Operation, ProductName, ProductCost)
                VALUES (?, ?, ?, ?)
                """
                cursor.execute(insert_query, (product_id, operation_str, product_name, product_cost))
                logging.info(f"Recorded trigger: ProductId={product_id}, Operation={operation_str}")
    except Exception as e:
        logging.error(f"Error processing SQL trigger: {e}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# ============================================================================
# HTTP endpoint to get tracked trigger invocations (for test verification)
# ============================================================================
@app.function_name(name="GetTrackedChanges")
@app.route(route="gettrackedchanges")
def get_tracked_changes(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP triggered function to retrieve tracked trigger changes.
    Used for verifying that SQL triggers are firing correctly.
    """
    try:
        odbc_connection_string = _get_odbc_connection_string()
        if not odbc_connection_string:
            return func.HttpResponse(
                json.dumps({"error": "SqlConnectionString not configured"}),
                status_code=500,
                mimetype="application/json"
            )
        
        conn = pyodbc.connect(odbc_connection_string, autocommit=True)
        cursor = None
        try:
            cursor = conn.cursor()
            
            # Get optional query parameters for filtering
            product_id = req.params.get('productId')
            operation = req.params.get('operation')
            
            query = "SELECT Id, ProductId, Operation, ProductName, ProductCost, RecordedAt FROM TriggerTracking WHERE 1=1"
            params = []
            
            if product_id:
                try:
                    product_id_int = int(product_id)
                except ValueError:
                    return func.HttpResponse(
                        json.dumps({"error": "Invalid productId; must be an integer"}),
                        status_code=400,
                        mimetype="application/json"
                    )
                query += " AND ProductId = ?"
                params.append(product_id_int)
            
            if operation:
                query += " AND Operation = ?"
                params.append(operation)
            
            query += " ORDER BY RecordedAt DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    "Id": row[0],
                    "ProductId": row[1],
                    "Operation": row[2],
                    "ProductName": row[3],
                    "ProductCost": row[4],
                    "RecordedAt": str(row[5])
                })
            
            return func.HttpResponse(
                json.dumps(results),
                status_code=200,
                mimetype="application/json"
            )
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()
    except Exception as e:
        logging.error(f"Error getting tracked changes: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# ============================================================================
# HTTP endpoint to clear tracked changes (for test cleanup)
# ============================================================================
@app.function_name(name="ClearTrackedChanges")
@app.route(route="cleartrackedchanges", methods=["POST", "DELETE"])
def clear_tracked_changes(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP triggered function to clear tracked trigger changes.
    Used for test cleanup.
    """
    try:
        odbc_connection_string = _get_odbc_connection_string()
        if not odbc_connection_string:
            return func.HttpResponse(
                json.dumps({"error": "SqlConnectionString not configured"}),
                status_code=500,
                mimetype="application/json"
            )
        
        conn = pyodbc.connect(odbc_connection_string, autocommit=True)
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM TriggerTracking")
            
            return func.HttpResponse(
                json.dumps({"message": "Tracked changes cleared"}),
                status_code=200,
                mimetype="application/json"
            )
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()
    except Exception as e:
        logging.error(f"Error clearing tracked changes: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
