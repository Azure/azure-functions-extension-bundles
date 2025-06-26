import azure.functions as func
import json
import logging
import azure.functions as azf

def main(req: azf.HttpRequest, changes: str):
    if changes:
        logging.info("MySQL Changes: ")
    
    json_changes = json.loads(changes)
    for change in json_changes:
        product = func.MySqlRow(change["Item"]) 
        logging.info(product.data)

    return changes
