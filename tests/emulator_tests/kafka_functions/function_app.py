import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Global storage for metadata trigger results (shared in-process)
_kafka_metadata_result = {}


# A Kafka trigger which stores the event value into a storage blob.
# The Kafka event body is a JSON envelope with Offset, Partition, Topic,
# Value, Headers, Key fields. We extract the Value field.
@app.function_name(name="kafka_trigger")
@app.kafka_trigger(arg_name="event",
                   topic="e2e-test-topic",
                   broker_list="BrokerList",
                   consumer_group="e2e_tests",
                   data_type="string")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-kafka-triggered.txt",
                 connection="AzureWebJobsStorage")
def kafka_trigger(event: func.KafkaEvent) -> str:
    body = event.get_body()
    event_data = json.loads(body)
    return event_data.get('Value', '')


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_kafka_triggered")
@app.route(route="get_kafka_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-kafka-triggered.txt",
                connection="AzureWebJobsStorage")
def get_kafka_triggered(req: func.HttpRequest,
                        file: func.InputStream) -> str:
    return file.read().decode('utf-8')


# An HttpTrigger to send a message to Kafka via the Kafka output binding
@app.function_name(name="kafka_output")
@app.route(route="kafka_output")
@app.kafka_output(arg_name="event",
                  topic="e2e-output-topic",
                  broker_list="BrokerList")
def kafka_output(req: func.HttpRequest, event: func.Out[str]):
    event.set(req.get_body().decode('utf-8'))
    return 'OK'


# A Kafka trigger on the output topic that stores the event value into blob
@app.function_name(name="kafka_output_trigger")
@app.kafka_trigger(arg_name="event",
                   topic="e2e-output-topic",
                   broker_list="BrokerList",
                   consumer_group="e2e_output_tests",
                   data_type="string")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-kafka-output-triggered.txt",
                 connection="AzureWebJobsStorage")
def kafka_output_trigger(event: func.KafkaEvent) -> str:
    body = event.get_body()
    event_data = json.loads(body)
    return event_data.get('Value', '')


# Retrieve the output binding trigger result from blob
@app.function_name(name="get_kafka_output_triggered")
@app.route(route="get_kafka_output_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-kafka-output-triggered.txt",
                connection="AzureWebJobsStorage")
def get_kafka_output_triggered(req: func.HttpRequest,
                               file: func.InputStream) -> str:
    return file.read().decode('utf-8')


# A Kafka trigger with metadata. Stores result in a global variable.
@app.function_name(name="kafka_metadata_trigger")
@app.kafka_trigger(arg_name="event",
                   topic="e2e-metadata-topic",
                   broker_list="BrokerList",
                   consumer_group="e2e_metadata_tests",
                   data_type="string")
def kafka_metadata_trigger(event: func.KafkaEvent):
    global _kafka_metadata_result
    body = event.get_body()
    event_data = json.loads(body)
    _kafka_metadata_result = {
        'body': event_data.get('Value', ''),
        'topic': event.topic,
        'partition': event.partition,
        'offset': event.offset,
        'key': event.key,
        'timestamp': event.timestamp,
    }


# Retrieve the metadata trigger result from in-process global variable
@app.function_name(name="get_kafka_metadata_triggered")
@app.route(route="get_kafka_metadata_triggered")
def get_kafka_metadata_triggered(req: func.HttpRequest) -> func.HttpResponse:
    if not _kafka_metadata_result:
        return func.HttpResponse(
            body='{}',
            mimetype="application/json",
            status_code=404,
        )
    return func.HttpResponse(
        body=json.dumps(_kafka_metadata_result),
        mimetype="application/json",
        status_code=200,
    )

