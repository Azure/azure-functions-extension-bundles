# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Azure Functions for testing CosmosDB bindings.

This module provides functions that test:
- CosmosDB Trigger (change feed)
- CosmosDB Input Binding (ID lookup and SQL queries)
- CosmosDB Output Binding (single and multiple documents)

Based on:
- https://learn.microsoft.com/azure/azure-functions/functions-bindings-cosmosdb-v2
- https://github.com/Azure/azure-webjobs-sdk-extensions/tree/dev/sample/ExtensionsSample
"""
import json
import logging
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Store triggered documents for verification (in-memory for tests)
_triggered_docs = []
_batch_triggered_docs = []

# =============================================================================
# COSMOS DB TRIGGER BINDINGS
# =============================================================================


@app.cosmos_db_trigger(
    arg_name="docs", database_name="test",
    container_name="items",
    lease_container_name="leases",
    connection="AzureWebJobsCosmosDBConnectionString",
    create_lease_container_if_not_exists=True)
@app.blob_output(arg_name="$return", connection="AzureWebJobsStorage",
                 path="bundle-tests/test-cosmosdb-triggered.txt")
def cosmosdb_trigger(docs: func.DocumentList) -> str:
    """Change feed trigger - writes first document to blob"""
    if not docs:
        logging.warning("Trigger received empty document list")
        return "{}"
    try:
        for doc in docs:
            _triggered_docs.append(json.loads(doc.to_json()))
        return docs[0].to_json()
    except (json.JSONDecodeError, IndexError) as e:
        logging.error(f"Error processing trigger documents: {e}")
        return json.dumps({"error": str(e)})


@app.cosmos_db_trigger(
    arg_name="docs",
    database_name="test",
    container_name="batch_items",
    lease_container_name="batch_leases",
    connection="AzureWebJobsCosmosDBConnectionString",
    create_lease_container_if_not_exists=True,
    max_items_per_invocation=5)
def cosmosdb_trigger_batch(docs: func.DocumentList):
    """Change feed trigger with max_items_per_invocation for batch processing"""
    logging.info(f"Batch trigger received {len(docs)} documents")
    batch = []
    for doc in docs:
        batch.append(json.loads(doc.to_json()))
    _batch_triggered_docs.append({
        "count": len(docs),
        "docs": batch
    })


@app.cosmos_db_trigger(
    arg_name="docs",
    database_name="test",
    container_name="feed_delay_items",
    lease_container_name="feed_delay_leases",
    connection="AzureWebJobsCosmosDBConnectionString",
    create_lease_container_if_not_exists=True,
    feed_poll_delay=1000)
@app.blob_output(arg_name="$return", connection="AzureWebJobsStorage",
                 path="bundle-tests/test-cosmosdb-feed-delay.txt")
def cosmosdb_trigger_feed_delay(docs: func.DocumentList) -> str:
    """Change feed trigger with custom feed_poll_delay (1 second)"""
    return json.dumps({
        "count": len(docs),
        "ids": [json.loads(doc.to_json()).get('id') for doc in docs]
    })


# =============================================================================
# COSMOS DB OUTPUT BINDINGS
# =============================================================================


@app.route(route="put_document")
@app.cosmos_db_output(
    arg_name="doc", database_name="test",
    container_name="items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString")
def put_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    """Output binding - write single document"""
    try:
        doc.set(func.Document.from_json(req.get_body()))
        return 'OK'
    except (ValueError, json.JSONDecodeError) as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON: {str(e)}"}),
            status_code=400, mimetype='application/json'
        )


@app.route(route="put_documents")
@app.cosmos_db_output(
    arg_name="docs",
    database_name="test",
    container_name="items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString")
def put_documents(req: func.HttpRequest, docs: func.Out[func.DocumentList]):
    """Output binding - write multiple documents at once"""
    try:
        body = json.loads(req.get_body())
        doc_list = func.DocumentList()
        for item in body:
            doc_list.append(func.Document.from_dict(item))
        docs.set(doc_list)
        return func.HttpResponse(
            json.dumps({"inserted": len(body)}),
            mimetype='application/json'
        )
    except (ValueError, json.JSONDecodeError) as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON: {str(e)}"}),
            status_code=400, mimetype='application/json'
        )


@app.route(route="put_nested_document")
@app.cosmos_db_output(
    arg_name="doc",
    database_name="test",
    container_name="items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString")
def put_nested_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    """Output binding - write document with nested structure"""
    try:
        doc.set(func.Document.from_json(req.get_body()))
        return 'OK'
    except (ValueError, json.JSONDecodeError) as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON: {str(e)}"}),
            status_code=400, mimetype='application/json'
        )


@app.route(route="put_batch_document")
@app.cosmos_db_output(
    arg_name="doc",
    database_name="test",
    container_name="batch_items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString")
def put_batch_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    """Output binding - write to batch_items container for batch trigger tests"""
    try:
        doc.set(func.Document.from_json(req.get_body()))
        return 'OK'
    except (ValueError, json.JSONDecodeError) as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON: {str(e)}"}),
            status_code=400, mimetype='application/json'
        )


@app.route(route="put_feed_delay_document")
@app.cosmos_db_output(
    arg_name="doc",
    database_name="test",
    container_name="feed_delay_items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString")
def put_feed_delay_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    """Output binding - write to feed_delay_items container"""
    try:
        doc.set(func.Document.from_json(req.get_body()))
        return 'OK'
    except (ValueError, json.JSONDecodeError) as e:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid JSON: {str(e)}"}),
            status_code=400, mimetype='application/json'
        )


# =============================================================================
# HELPER ENDPOINTS FOR TEST VERIFICATION
# =============================================================================


@app.route(route="get_cosmosdb_triggered")
@app.blob_input(arg_name="file", connection="AzureWebJobsStorage",
                path="bundle-tests/test-cosmosdb-triggered.txt")
def get_cosmosdb_triggered(req: func.HttpRequest,
                           file: func.InputStream) -> str:
    """Get the content written by cosmosdb_trigger"""
    return file.read().decode('utf-8')


@app.route(route="get_feed_delay_triggered")
@app.blob_input(arg_name="file", connection="AzureWebJobsStorage",
                path="bundle-tests/test-cosmosdb-feed-delay.txt")
def get_feed_delay_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    """Get the content written by cosmosdb_trigger_feed_delay"""
    return file.read().decode('utf-8')


@app.route(route="get_triggered_docs")
def get_triggered_docs(req: func.HttpRequest) -> str:
    """Get all documents that were received by triggers (in-memory)"""
    return func.HttpResponse(
        json.dumps(_triggered_docs),
        mimetype='application/json'
    )


@app.route(route="get_batch_triggered_docs")
def get_batch_triggered_docs(req: func.HttpRequest) -> str:
    """Get batch trigger invocation records"""
    return func.HttpResponse(
        json.dumps(_batch_triggered_docs),
        mimetype='application/json'
    )


@app.route(route="clear_triggered_docs", methods=["POST", "DELETE"])
def clear_triggered_docs(req: func.HttpRequest) -> str:
    """Clear in-memory triggered docs for test isolation"""
    global _triggered_docs, _batch_triggered_docs
    _triggered_docs = []
    _batch_triggered_docs = []
    return func.HttpResponse('{"cleared": true}', mimetype='application/json')
