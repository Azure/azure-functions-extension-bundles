# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pathlib
import time

from tests.utils import testutils


class TestTableFunctionsStein(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'table_functions'
    
    def test_table_bindings(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        row_key = json.loads(out_resp.text)['RowKey']

        in_resp = self.webhost.request('GET', f'table_in_binding/{row_key}')
        self.assertEqual(in_resp.status_code, 200)
        row_key_present = False
        for row in json.loads(in_resp.text):
            if row["RowKey"] == row_key:
                row_key_present = True
                break
        self.assertTrue(row_key_present)

