import azure.functions as func
import datetime
import json
import logging

app = func.FunctionApp()

# An HTTP-Triggered Function with a Durable Functions Client binding
@app.route(route="orchestrators/{functionName}")
@app.durable_client_input(client_name="client")
async def hello_orchestration_starter(req: func.HttpRequest, client):
    function_name = req.route_params.get('functionName')
    instance_id = await client.start_new(function_name)
    response = client.create_check_status_response(req, instance_id)
    return response


# Orchestrator
@app.orchestration_trigger(context_name="context")
def hello_orchestration_orchestrator(context):
    result1 = yield context.call_activity("hello_orchestration_activity", "Seattle")
    result2 = yield context.call_activity("hello_orchestration_activity", "Tokyo")
    result3 = yield context.call_activity("hello_orchestration_activity", "London")

    return [result1, result2, result3]

# Activity
@app.activity_trigger(input_name="city")
def hello_orchestration_activity(city: str):
    return "Hello " + city 


# Fan-out/Fan-in orchestrator using task_all
@app.orchestration_trigger(context_name="context")
def fan_out_in_orchestrator(context):
    items = [1, 2, 3, 4, 5]
    tasks = [context.call_activity("square_activity", i) for i in items]
    results = yield context.task_all(tasks)
    return results


@app.activity_trigger(input_name="n")
def square_activity(n: int):
    return n * n


# Chaining orchestrator: two-step chaining
@app.orchestration_trigger(context_name="context")
def chaining_orchestrator(context):
    first = yield context.call_activity("simple_generate_activity", None)
    second = yield context.call_activity("simple_append_activity", first)
    return second


@app.activity_trigger(input_name="_unused")
def simple_generate_activity(_unused):
    return "hello"


@app.activity_trigger(input_name="s")
def simple_append_activity(s: str):
    return f"{s} world"


# Sub-orchestration: parent calls child orchestrator
@app.orchestration_trigger(context_name="context")
def sub_parent_orchestrator(context):
    child_result = yield context.call_sub_orchestrator("sub_child_orchestrator", "ping")
    return f"parent->{child_result}"


@app.orchestration_trigger(context_name="context")
def sub_child_orchestrator(context):
    inp = context.get_input()
    echoed = yield context.call_activity("echo_activity", inp)
    return f"child:{echoed}"


@app.activity_trigger(input_name="x")
def echo_activity(x):
    return x