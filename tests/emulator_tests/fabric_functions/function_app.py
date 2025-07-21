# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import fabric.functions as fn

udf = fn.UserDataFunctions()

@udf.function()
def test_hello_fabric() -> str:
    return f"Welcome to Fabric Functions"

@udf.function()
def test_add_parameters(stringParam:str, numParam:int) -> str:
    return f"stringParam: {stringParam}, numParam: {numParam}"

@udf.connection(alias="mockConnection", argName="mockSqlDB")
@udf.function()
def test_add_connection(mockSqlDB: fn.FabricSqlConnection) -> dict:
    # Testing to make sure the endpoints are injected correctly by the host extension
    
    return {"mockSqlDB": mockSqlDB.endpoints}

@udf.context(argName="myContext")
@udf.function()
def test_add_fabriccontext(myContext: fn.UserDataFunctionContext) -> dict:
    return  {
        "invocationId": myContext.invocation_id,
        "executingUser": myContext.executing_user
    }