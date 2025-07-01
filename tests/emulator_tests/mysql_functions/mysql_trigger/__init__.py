# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import mysql_test_utils
import mysql.connector

def main(changes: str) :
    """
    Function to handle MySQL trigger events.

    Arguments:
    changes: The list of updated objects returned by the MySql trigger binding
    """
    person_dao = mysql_test_utils.PersonDAO()

    json_changes = json.loads(changes)
    try:
        # update the address column with the string "Function Triggered" for each row
        # to indicate that the function was triggered
        for change in json_changes:
            person_dao.update_address_column(change["Item"]["id"])
            logging.info(f"Updated address column for triggered row: {change["Item"]["id"]}")
    except mysql.connector.Error as err:
        logging.error(f"Error encountered while trying to update address column: {err}")
