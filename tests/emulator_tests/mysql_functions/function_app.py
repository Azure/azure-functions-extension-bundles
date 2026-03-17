# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import mysql_test_utils
import mysql.connector
import azure.functions as func

# Create a FunctionApp instance using the v2 programming model
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# ============================================================================
# MySQL Input Binding - Get products by cost
# ============================================================================
@app.function_name(name="GetProducts")
@app.route(route="getproducts/{cost}")
@app.mysql_input(arg_name="products",
                 command_text="SELECT * FROM Products WHERE Cost = @Cost",
                 command_type="Text",
                 parameters="@Cost={cost}",
                 connection_string_setting="MySqlConnectionString")
def get_products(req: func.HttpRequest, products: func.MySqlRowList) -> func.HttpResponse:
    """
    HTTP triggered function with MySQL input binding.
    Returns products where Cost matches the specified value.
    """
    rows = list(map(lambda r: json.loads(r.to_json()), products))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )


# ============================================================================
# MySQL Input Binding - Get product by ID
# ============================================================================
@app.function_name(name="GetProductById")
@app.route(route="getproduct/{id}")
@app.mysql_input(arg_name="products",
                 command_text="SELECT * FROM Products WHERE ProductId = @ProductId",
                 command_type="Text",
                 parameters="@ProductId={id}",
                 connection_string_setting="MySqlConnectionString")
def get_product_by_id(req: func.HttpRequest, products: func.MySqlRowList) -> func.HttpResponse:
    """
    HTTP triggered function with MySQL input binding.
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
# MySQL Output Binding - Add/Upsert a single product
# ============================================================================
@app.function_name(name="AddProduct")
@app.route(route="addproduct")
@app.mysql_output(arg_name="product",
                  command_text="Products",
                  connection_string_setting="MySqlConnectionString")
def add_product(req: func.HttpRequest, product: func.Out[func.MySqlRow]) -> func.HttpResponse:
    """
    HTTP triggered function with MySQL output binding.
    Upserts a product - inserts if ProductId doesn't exist, updates if it does.
    """
    try:
        body = json.loads(req.get_body())
        row = func.MySqlRow.from_dict(body)
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
# MySQL Output Binding - Add multiple products
# ============================================================================
@app.function_name(name="AddProducts")
@app.route(route="addproducts")
@app.mysql_output(arg_name="products",
                  command_text="Products",
                  connection_string_setting="MySqlConnectionString")
def add_products(req: func.HttpRequest, products: func.Out[func.MySqlRowList]) -> func.HttpResponse:
    """
    HTTP triggered function with MySQL output binding.
    Upserts multiple products at once.
    """
    try:
        body = json.loads(req.get_body())
        rows = func.MySqlRowList(map(lambda r: func.MySqlRow.from_dict(r), body))
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
# MySQL Trigger Binding - React to changes in Products table
# ============================================================================
@app.function_name(name="ProductsTrigger")
@app.mysql_trigger(arg_name="changes",
                   table_name="Products",
                   connection_string_setting="MySqlConnectionString")
def products_trigger(changes: str) -> None:
    """
    MySQL trigger function that fires when changes occur in the Products table.
    Records the changes to TriggerTracking table for verification.
    """
    logging.info(f"MySQL Changes: {changes}")

    trigger_tracking_dao = mysql_test_utils.TriggerTrackingDAO()

    try:
        # Parse the changes
        change_list = json.loads(changes)

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
            trigger_tracking_dao.insert_tracking_record(
                product_id, operation_str, product_name, product_cost
            )
            logging.info(f"Recorded trigger: ProductId={product_id}, Operation={operation_str}")

    except Exception as e:
        logging.error(f"Error processing MySQL trigger: {e}")


# ============================================================================
# HTTP endpoint to get tracked trigger invocations (for test verification)
# ============================================================================
@app.function_name(name="GetTrackedChanges")
@app.route(route="gettrackedchanges")
def get_tracked_changes(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP triggered function to retrieve tracked trigger changes.
    Used for verifying that MySQL triggers are firing correctly.
    """
    try:
        trigger_tracking_dao = mysql_test_utils.TriggerTrackingDAO()

        # Get optional query parameters for filtering
        product_id = req.params.get('productId')
        operation = req.params.get('operation')

        product_id_int = None
        if product_id:
            try:
                product_id_int = int(product_id)
            except ValueError:
                return func.HttpResponse(
                    json.dumps({"error": "Invalid productId; must be an integer"}),
                    status_code=400,
                    mimetype="application/json"
                )

        rows = trigger_tracking_dao.get_tracked_changes(product_id_int, operation)

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
        trigger_tracking_dao = mysql_test_utils.TriggerTrackingDAO()
        trigger_tracking_dao.clear_tracked_changes()

        return func.HttpResponse(
            json.dumps({"message": "Tracked changes cleared"}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error clearing tracked changes: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# ============================================================================
# MySQL Output Binding - Add product with identity column (AUTO_INCREMENT)
# ============================================================================
@app.function_name(name="AddProductWithIdentity")
@app.route(route="addproductwithidentity")
@app.mysql_output(arg_name="product",
                  command_text="ProductsWithIdentity",
                  connection_string_setting="MySqlConnectionString")
def add_product_with_identity(req: func.HttpRequest, product: func.Out[func.MySqlRow]) -> func.HttpResponse:
    """
    HTTP triggered function with MySQL output binding.
    Inserts a product into a table with AUTO_INCREMENT primary key.
    The ProductId is generated automatically.
    """
    try:
        body = json.loads(req.get_body())
        row = func.MySqlRow.from_dict(body)
        product.set(row)

        return func.HttpResponse(
            body=req.get_body(),
            status_code=201,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error adding product with identity: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json"
        )


# ============================================================================
# MySQL Combined Input + Output Binding - Get and copy products
# ============================================================================
@app.function_name(name="GetAndAddProducts")
@app.route(route="getandaddproducts/{cost}")
@app.mysql_input(arg_name="products",
                 command_text="SELECT * FROM Products WHERE Cost = @Cost",
                 command_type="Text",
                 parameters="@Cost={cost}",
                 connection_string_setting="MySqlConnectionString")
@app.mysql_output(arg_name="productsWithIdentity",
                  command_text="ProductsWithIdentity",
                  connection_string_setting="MySqlConnectionString")
def get_and_add_products(req: func.HttpRequest,
                         products: func.MySqlRowList,
                         productsWithIdentity: func.Out[func.MySqlRowList]) -> func.HttpResponse:
    """
    HTTP triggered function with combined MySQL input and output bindings.
    Gets products from Products table and upserts them to ProductsWithIdentity table.
    """
    try:
        productsWithIdentity.set(products)

        rows = list(map(lambda r: json.loads(r.to_json()), products))
        return func.HttpResponse(
            json.dumps(rows),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error in get and add products: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# ============================================================================
# Legacy MySQL Trigger for person table (keep for backward compatibility)
# ============================================================================
@app.mysql_trigger(arg_name="changes",
                   table_name="person",
                   connection_string_setting="MySqlConnectionString")
def mysql_trigger_function(changes: str) -> None:
    """
    Function to handle MySQL trigger events using Azure Functions v2 programming model.

    Arguments:
    changes: The list of updated objects returned by the MySql trigger binding
    """
    person_dao = mysql_test_utils.PersonDAO()

    try:
        json_changes = json.loads(changes)
        for change in json_changes:
            person_dao.update_address_column(change["Item"]["id"])
            logging.info(f"Updated address column for triggered row: {change['Item']['id']}")
    except mysql.connector.Error as err:
        logging.error(f"Error encountered while trying to update address column: {err}")
    except Exception as err:
        logging.error(f"Unexpected error in MySQL trigger function: {err}")
