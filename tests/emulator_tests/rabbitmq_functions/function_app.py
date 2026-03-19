# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
RabbitMQ E2E Test Functions for Python
Uses the v2 programming model with decorators
"""

import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# A RabbitMQ trigger which stores the message value into a storage blob.
@app.function_name(name="rabbitmq_trigger")
@app.generic_trigger(
    arg_name="message",
    type="rabbitmqtrigger",
    connectionStringSetting="RabbitMQConnectionString",
    queueName="e2e-test-queue",
    data_type="string"
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/test-rabbitmq-triggered.txt",
    connection="AzureWebJobsStorage"
)
def rabbitmq_trigger(message: str) -> str:
    logging.info(f'RabbitMQ trigger received message: {message}')
    return message


# Retrieve the message from storage blob and return it as HTTP response
@app.function_name(name="get_rabbitmq_triggered")
@app.route(route="get_rabbitmq_triggered")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/test-rabbitmq-triggered.txt",
    connection="AzureWebJobsStorage"
)
def get_rabbitmq_triggered(req: func.HttpRequest,
                           file: func.InputStream) -> str:
    return file.read().decode('utf-8')


# An HttpTrigger to send a message to RabbitMQ via the RabbitMQ output binding
@app.function_name(name="rabbitmq_output")
@app.route(route="rabbitmq_output")
@app.generic_output_binding(
    arg_name="rabbitmqOutput",
    type="rabbitmq",
    connectionStringSetting="RabbitMQConnectionString",
    queueName="e2e-output-queue"
)
def rabbitmq_output(req: func.HttpRequest,
                    rabbitmqOutput: func.Out[str]) -> str:
    message = req.get_body().decode('utf-8')
    logging.info(f'Sending message to RabbitMQ: {message}')
    rabbitmqOutput.set(message)
    return 'OK'


# A RabbitMQ trigger on the output queue that stores the message into blob
@app.function_name(name="rabbitmq_output_trigger")
@app.generic_trigger(
    arg_name="message",
    type="rabbitmqtrigger",
    connectionStringSetting="RabbitMQConnectionString",
    queueName="e2e-output-queue",
    data_type="string"
)
@app.blob_output(
    arg_name="$return",
    path="bundle-tests/test-rabbitmq-output-triggered.txt",
    connection="AzureWebJobsStorage"
)
def rabbitmq_output_trigger(message: str) -> str:
    logging.info(f'RabbitMQ output trigger received message: {message}')
    return message


# Retrieve the output binding trigger result from blob
@app.function_name(name="get_rabbitmq_output_triggered")
@app.route(route="get_rabbitmq_output_triggered")
@app.blob_input(
    arg_name="file",
    path="bundle-tests/test-rabbitmq-output-triggered.txt",
    connection="AzureWebJobsStorage"
)
def get_rabbitmq_output_triggered(req: func.HttpRequest,
                                  file: func.InputStream) -> str:
    return file.read().decode('utf-8')
