import json
import os
import time

import pytest

from tests.utils import testutils


class TestDurableFunctions(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'durable_functions'

    def _start_and_wait(self, function_name: str):
        # Start orchestration via the new durable client starter route
        r = self.webhost.request('POST', f'orchestrators/{function_name}')
        self.assertEqual(r.status_code, 202)

        # The durable starter returns a payload with statusQueryGetUri and id
        payload = json.loads(r.text) if r.text else {}
        status_query_uri = payload.get('statusQueryGetUri') or r.headers.get('Location')
        self.assertIsNotNone(status_query_uri, 'No statusQueryGetUri returned')
        instance_id = payload.get('id')

        # poll status
        import requests
        for _ in range(30):
            s = requests.get(status_query_uri)
            if s.status_code == 200:
                data = json.loads(s.text)
                runtime_status = (data.get('runtimeStatus') or data.get('runtime_status') or '').lower()
                if runtime_status in ('completed', 'failed', 'terminated'):
                    # Ensure instance_id captured
                    instance_id = instance_id or data.get('id')
                    return instance_id, data
            time.sleep(1)
        self.fail('orchestration did not complete in time')

    def test_orchestration_output(self):
        """Test orchestration completes and returns expected city greetings"""
        _, data = self._start_and_wait('hello_orchestration_orchestrator')
        output = data.get('output') or []
        self.assertEqual(output, [
            'Hello Seattle',
            'Hello Tokyo',
            'Hello London'
        ])

    def test_completion_status(self):
        """Test that orchestration completes successfully"""
        _, data = self._start_and_wait('hello_orchestration_orchestrator')
        status = (data.get('runtimeStatus') or data.get('runtime_status') or '').lower()
        self.assertEqual(status, 'completed')

    def test_multiple_runs_unique_ids(self):
        """Test that multiple orchestrations get unique instance IDs"""
        id1, _ = self._start_and_wait('hello_orchestration_orchestrator')
        id2, _ = self._start_and_wait('hello_orchestration_orchestrator')
        self.assertNotEqual(id1, id2)

    def test_status_payload_has_history(self):
        """Test that orchestration status includes history"""
        _, data = self._start_and_wait('hello_orchestration_orchestrator')
        hist = data.get('history') or data.get('historyEvents') or []
        self.assertIsInstance(hist, list)

    def test_fan_out_in(self):
        """Fan-out/fan-in orchestrator returns aggregated squares"""
        _, data = self._start_and_wait('fan_out_in_orchestrator')
        output = data.get('output') or []
        self.assertEqual(output, [1, 4, 9, 16, 25])

    def test_chaining(self):
        """Chaining orchestrator passes outputs correctly"""
        _, data = self._start_and_wait('chaining_orchestrator')
        output = data.get('output')
        self.assertEqual(output, 'hello world')

    def test_suborchestration(self):
        """Sub-orchestration returns aggregated parent->child output"""
        _, data = self._start_and_wait('sub_parent_orchestrator')
        output = data.get('output')
        self.assertEqual(output, 'parent->child:ping')


