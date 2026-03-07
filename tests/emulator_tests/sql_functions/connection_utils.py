# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Shared SQL connection string utilities for Azure Functions SQL extension tests."""

import os
from typing import Optional


def convert_ado_to_odbc(ado_connection_string: str) -> str:
    """Convert ADO.NET connection string to ODBC format for pyodbc.

    ADO.NET format: Server=localhost,1433;Database=testdb;User Id=sa;Password=xxx;TrustServerCertificate=True
    ODBC format: Driver={ODBC Driver 18 for SQL Server};Server=localhost,1433;Database=testdb;UID=sa;PWD=xxx;TrustServerCertificate=yes
    """
    # Parse the connection string
    params = {}
    for part in ado_connection_string.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.strip().lower()] = value.strip()

    # Map ADO.NET keys to ODBC keys
    server = params.get('server', 'localhost,1433')
    database = params.get('database', 'testdb')
    user = params.get('user id', params.get('uid', 'sa'))
    password = params.get('password', params.get('pwd', ''))
    trust_cert = params.get('trustservercertificate', 'True').lower() in ('true', 'yes', '1')

    # Build ODBC connection string
    odbc_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate={'yes' if trust_cert else 'no'};"
    )

    return odbc_string


def get_odbc_connection_string() -> Optional[str]:
    """Get ODBC-formatted connection string from environment variable."""
    connection_string = os.environ.get("SqlConnectionString")
    if connection_string:
        return convert_ado_to_odbc(connection_string)
    return None
