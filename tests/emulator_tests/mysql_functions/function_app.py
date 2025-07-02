# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import mysql_test_utils
import mysql.connector
import azure.functions as func

# Create a FunctionApp instance using the v2 programming model
app = func.FunctionApp()

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
        # update the address column with the string "Function Triggered" for each row
        # to indicate that the function was triggered
        json_changes = json.loads(changes)
        for change in json_changes:
            person_dao.update_address_column(change["Item"]["id"])
            logging.info(f"Updated address column for triggered row: {change['Item']['id']}")
    except mysql.connector.Error as err:
        logging.error(f"Error encountered while trying to update address column: {err}")
    except Exception as err:
        logging.error(f"Unexpected error in MySQL trigger function: {err}")
