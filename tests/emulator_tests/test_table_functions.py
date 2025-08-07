# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import pathlib
import time

from tests.utils import testutils

logger = logging.getLogger(__name__)


class TestTableFunctionsStein(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'table_functions'
    
    def test_table_bindings(self):
        # Create table entry using output binding
        logger.info("Creating table entry with output binding...")
        out_resp = self.webhost.request('POST', 'table_out_binding',
                                       max_retries=3,
                                       expected_status=200)
        row_key = json.loads(out_resp.text)['RowKey']

        # Retrieve table entry using input binding with retry
        logger.info(f"Retrieving table entry with row key: {row_key}")
        in_resp = self.webhost.wait_and_request('GET', f'table_in_binding/{row_key}',
                                               wait_time=2,
                                               max_retries=10,
                                               expected_status=200)
        
        # Verify the row key is present in the response
        row_key_present = False
        for row in json.loads(in_resp.text):
            if row["RowKey"] == row_key:
                row_key_present = True
                break
        self.assertTrue(row_key_present)

