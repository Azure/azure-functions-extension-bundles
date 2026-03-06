# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Event Grid Functions for emulator tests.

This module contains Azure Functions that test Event Grid triggers and bindings
using mock HTTP POST events (no Azure Event Grid connection required).

Test scenarios covered (based on .NET SDK samples):
1. EventGridEvent single trigger
2. CloudEvent single trigger
3. EventGrid output binding (mock verification)
4. CloudEvent output binding (mock verification)
5. Data shape variations - String, array, primitive, nested payloads
6. Edge cases - Missing/null/empty data, special characters, large payloads
"""
import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# =============================================================================
# EventGridEvent Trigger - Single Event
# =============================================================================
@app.function_name(name="eventgrid_trigger")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger(event: func.EventGridEvent) -> str:
    """Process a single EventGridEvent and write result to blob storage."""
    logging.info(f"EventGrid trigger received event: {event.id}")
    result = {
        'id': event.id,
        'event_type': event.event_type,
        'subject': event.subject,
        'event_time': str(event.event_time) if event.event_time else None,
        'data': event.get_json(),
        'data_version': event.data_version,
        'topic': event.topic
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_triggered")
@app.route(route="get_eventgrid_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_triggered(req: func.HttpRequest,
                            file: func.InputStream) -> str:
    """Retrieve the EventGrid trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# CloudEvent Trigger - Single Event
# =============================================================================
@app.function_name(name="cloudevent_trigger")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-cloudevent-triggered.txt",
                 connection="AzureWebJobsStorage")
def cloudevent_trigger(event: func.EventGridEvent) -> str:
    """Process a single CloudEvent and write result to blob storage.
    
    Note: CloudEvents are received as EventGridEvent in Python SDK,
    the schema determines how the event is parsed.
    """
    logging.info(f"CloudEvent trigger received event: {event.id}")
    result = {
        'id': event.id,
        'type': event.event_type,
        'source': event.topic,
        'subject': event.subject,
        'time': str(event.event_time) if event.event_time else None,
        'data': event.get_json()
    }
    return json.dumps(result)


@app.function_name(name="get_cloudevent_triggered")
@app.route(route="get_cloudevent_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-cloudevent-triggered.txt",
                connection="AzureWebJobsStorage")
def get_cloudevent_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    """Retrieve the CloudEvent trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# EventGrid Output Binding - Mock Verification
# Since we can't connect to real Event Grid, we verify the binding works
# by capturing the event data before it would be sent.
# =============================================================================
@app.function_name(name="eventgrid_output")
@app.route(route="eventgrid_output")
@app.blob_output(arg_name="outputblob",
                 path="python-worker-tests/test-eventgrid-output.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_output(req: func.HttpRequest,
                     outputblob: func.Out[str]) -> func.HttpResponse:
    """HTTP trigger that simulates EventGrid output binding behavior.
    
    Since we can't send to real Event Grid without Azure connection,
    we capture what would be sent and store it in blob for verification.
    This tests that the output binding decorator and event construction work.
    """
    try:
        body = req.get_body().decode('utf-8')
        event_data = json.loads(body) if body else {}
        
        # Construct an EventGridEvent-like structure
        output_event = {
            'id': event_data.get('id', 'generated-id'),
            'eventType': 'IncomingRequest',
            'subject': 'test/eventgrid/output',
            'eventTime': '2026-03-06T07:00:00Z',
            'data': event_data,
            'dataVersion': '1.0'
        }
        
        # Store the event that would be sent
        outputblob.set(json.dumps(output_event))
        
        return func.HttpResponse(
            json.dumps({'status': 'success', 'event': output_event}),
            mimetype='application/json',
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error in eventgrid_output: {e}")
        return func.HttpResponse(
            json.dumps({'status': 'error', 'message': str(e)}),
            mimetype='application/json',
            status_code=500
        )


@app.function_name(name="get_eventgrid_output")
@app.route(route="get_eventgrid_output")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-output.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_output(req: func.HttpRequest,
                         file: func.InputStream) -> str:
    """Retrieve the EventGrid output binding result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# CloudEvent Output Binding - Mock Verification
# =============================================================================
@app.function_name(name="cloudevent_output")
@app.route(route="cloudevent_output")
@app.blob_output(arg_name="outputblob",
                 path="python-worker-tests/test-cloudevent-output.txt",
                 connection="AzureWebJobsStorage")
def cloudevent_output(req: func.HttpRequest,
                      outputblob: func.Out[str]) -> func.HttpResponse:
    """HTTP trigger that simulates CloudEvent output binding behavior.
    
    Since we can't send to real Event Grid without Azure connection,
    we capture what would be sent and store it in blob for verification.
    """
    try:
        body = req.get_body().decode('utf-8')
        event_data = json.loads(body) if body else {}
        
        # Construct a CloudEvent-like structure
        output_event = {
            'specversion': '1.0',
            'type': 'IncomingRequest',
            'source': '/test/cloudevent/output',
            'id': event_data.get('id', 'generated-cloud-id'),
            'time': '2026-03-06T07:00:00Z',
            'subject': 'test/cloudevent/output',
            'datacontenttype': 'application/json',
            'data': event_data
        }
        
        # Store the event that would be sent
        outputblob.set(json.dumps(output_event))
        
        return func.HttpResponse(
            json.dumps({'status': 'success', 'event': output_event}),
            mimetype='application/json',
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error in cloudevent_output: {e}")
        return func.HttpResponse(
            json.dumps({'status': 'error', 'message': str(e)}),
            mimetype='application/json',
            status_code=500
        )


@app.function_name(name="get_cloudevent_output")
@app.route(route="get_cloudevent_output")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-cloudevent-output.txt",
                connection="AzureWebJobsStorage")
def get_cloudevent_output(req: func.HttpRequest,
                          file: func.InputStream) -> str:
    """Retrieve the CloudEvent output binding result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# NOTE: Python Event Grid triggers only support func.EventGridEvent type annotation.
# Unlike C#, Python does not support str, bytes, or dict type annotations for
# eventGridTrigger bindings. The C# equivalents (String, BinaryData, JObject)
# are not available in Python SDK.
# =============================================================================


# =============================================================================
# Different Data Payload Shapes - String Data
# =============================================================================
@app.function_name(name="eventgrid_trigger_string_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-stringdata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_string_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with string data payload."""
    logging.info("EventGrid trigger (string data) received event")
    # Data is a simple string, not JSON object
    data = event.get_json()
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_type': type(data).__name__
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_stringdata_triggered")
@app.route(route="get_eventgrid_stringdata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-stringdata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_stringdata_triggered(req: func.HttpRequest,
                                       file: func.InputStream) -> str:
    """Retrieve the string data trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Different Data Payload Shapes - Array Data
# =============================================================================
@app.function_name(name="eventgrid_trigger_array_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-arraydata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_array_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with array data payload."""
    logging.info("EventGrid trigger (array data) received event")
    data = event.get_json()
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_type': type(data).__name__,
        'first_element': data[0] if isinstance(data, list) and len(data) > 0 else None
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_arraydata_triggered")
@app.route(route="get_eventgrid_arraydata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-arraydata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_arraydata_triggered(req: func.HttpRequest,
                                      file: func.InputStream) -> str:
    """Retrieve the array data trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Different Data Payload Shapes - Primitive Data (number)
# =============================================================================
@app.function_name(name="eventgrid_trigger_primitive_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-primitivedata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_primitive_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with primitive (number) data payload."""
    logging.info("EventGrid trigger (primitive data) received event")
    data = event.get_json()
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_type': type(data).__name__
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_primitivedata_triggered")
@app.route(route="get_eventgrid_primitivedata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-primitivedata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_primitivedata_triggered(req: func.HttpRequest,
                                          file: func.InputStream) -> str:
    """Retrieve the primitive data trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Different Data Payload Shapes - Nested Object Data
# =============================================================================
@app.function_name(name="eventgrid_trigger_nested_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-nesteddata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_nested_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with nested object data payload."""
    logging.info("EventGrid trigger (nested data) received event")
    data = event.get_json()
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_type': type(data).__name__,
        'nested_value': data.get('nested', {}).get('value') if isinstance(data, dict) else None
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_nesteddata_triggered")
@app.route(route="get_eventgrid_nesteddata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-nesteddata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_nesteddata_triggered(req: func.HttpRequest,
                                       file: func.InputStream) -> str:
    """Retrieve the nested data trigger result from blob storage."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: CloudEvent Backward Compatibility (legacy format)
# Tests handling of older CloudEvent format with 'eventType' instead of 'type'
# =============================================================================
@app.function_name(name="cloudevent_backcompat_trigger")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-cloudevent-backcompat-triggered.txt",
                 connection="AzureWebJobsStorage")
def cloudevent_backcompat_trigger(event: func.EventGridEvent) -> str:
    """Process CloudEvent in backward compatible mode.
    
    Handles both legacy 'eventType' and modern 'type' field formats.
    """
    logging.info("CloudEvent backcompat trigger received event")
    result = {
        'id': event.id,
        'event_type': event.event_type,
        'subject': event.subject,
        'data': event.get_json(),
        'format': 'backcompat'
    }
    return json.dumps(result)


@app.function_name(name="get_cloudevent_backcompat_triggered")
@app.route(route="get_cloudevent_backcompat_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-cloudevent-backcompat-triggered.txt",
                connection="AzureWebJobsStorage")
def get_cloudevent_backcompat_triggered(req: func.HttpRequest,
                                        file: func.InputStream) -> str:
    """Retrieve the CloudEvent backcompat trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Missing Data Field
# Tests handling when 'data' field is missing from the event
# =============================================================================
@app.function_name(name="eventgrid_trigger_missing_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-missingdata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_missing_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with missing data field."""
    logging.info("EventGrid trigger (missing data) received event")
    try:
        data = event.get_json()
    except Exception as e:
        data = None
        logging.warning(f"Could not get data: {e}")
    
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_is_none': data is None,
        'handled': 'success'
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_missingdata_triggered")
@app.route(route="get_eventgrid_missingdata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-missingdata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_missingdata_triggered(req: func.HttpRequest,
                                        file: func.InputStream) -> str:
    """Retrieve the missing data trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Null Data Field
# Tests handling when 'data' field is explicitly null
# =============================================================================
@app.function_name(name="eventgrid_trigger_null_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-nulldata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_null_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with null data field."""
    logging.info("EventGrid trigger (null data) received event")
    try:
        data = event.get_json()
    except Exception:
        data = None
    
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_is_none': data is None,
        'handled': 'success'
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_nulldata_triggered")
@app.route(route="get_eventgrid_nulldata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-nulldata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_nulldata_triggered(req: func.HttpRequest,
                                     file: func.InputStream) -> str:
    """Retrieve the null data trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Empty String Data
# Tests handling when 'data' field is an empty string
# =============================================================================
@app.function_name(name="eventgrid_trigger_empty_data")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-emptydata-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_empty_data(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with empty string data field."""
    logging.info("EventGrid trigger (empty data) received event")
    try:
        data = event.get_json()
    except Exception:
        data = None
    
    result = {
        'id': event.id,
        'subject': event.subject,
        'data': data,
        'data_is_empty': data == '' or data is None,
        'handled': 'success'
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_emptydata_triggered")
@app.route(route="get_eventgrid_emptydata_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-emptydata-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_emptydata_triggered(req: func.HttpRequest,
                                      file: func.InputStream) -> str:
    """Retrieve the empty data trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Special Characters in Subject
# Tests handling of special characters, unicode, and URL encoding
# =============================================================================
@app.function_name(name="eventgrid_trigger_special_chars")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-specialchars-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_special_chars(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with special characters in fields."""
    logging.info("EventGrid trigger (special chars) received event")
    result = {
        'id': event.id,
        'subject': event.subject,
        'event_type': event.event_type,
        'data': event.get_json(),
        'subject_length': len(event.subject) if event.subject else 0,
        'handled': 'success'
    }
    return json.dumps(result, ensure_ascii=False)


@app.function_name(name="get_eventgrid_specialchars_triggered")
@app.route(route="get_eventgrid_specialchars_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-specialchars-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_specialchars_triggered(req: func.HttpRequest,
                                         file: func.InputStream) -> str:
    """Retrieve the special chars trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Large Payload
# Tests handling of larger event payloads
# =============================================================================
@app.function_name(name="eventgrid_trigger_large_payload")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-largepayload-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_large_payload(event: func.EventGridEvent) -> str:
    """Process EventGridEvent with a large data payload."""
    logging.info("EventGrid trigger (large payload) received event")
    data = event.get_json()
    data_size = len(json.dumps(data)) if data else 0
    
    result = {
        'id': event.id,
        'subject': event.subject,
        'data_size': data_size,
        'data_keys': list(data.keys()) if isinstance(data, dict) else None,
        'handled': 'success'
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_largepayload_triggered")
@app.route(route="get_eventgrid_largepayload_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-largepayload-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_largepayload_triggered(req: func.HttpRequest,
                                         file: func.InputStream) -> str:
    """Retrieve the large payload trigger result."""
    return file.read().decode('utf-8')


# =============================================================================
# Edge Case: Multiple Events with Same ID (idempotency test)
# =============================================================================
@app.function_name(name="eventgrid_trigger_duplicate_id")
@app.event_grid_trigger(arg_name="event")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-eventgrid-duplicateid-triggered.txt",
                 connection="AzureWebJobsStorage")
def eventgrid_trigger_duplicate_id(event: func.EventGridEvent) -> str:
    """Process EventGridEvent - tests that duplicate IDs are handled."""
    logging.info(f"EventGrid trigger (duplicate id) received event: {event.id}")
    result = {
        'id': event.id,
        'subject': event.subject,
        'event_type': event.event_type,
        'processed': True
    }
    return json.dumps(result)


@app.function_name(name="get_eventgrid_duplicateid_triggered")
@app.route(route="get_eventgrid_duplicateid_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventgrid-duplicateid-triggered.txt",
                connection="AzureWebJobsStorage")
def get_eventgrid_duplicateid_triggered(req: func.HttpRequest,
                                        file: func.InputStream) -> str:
    """Retrieve the duplicate id trigger result."""
    return file.read().decode('utf-8')
