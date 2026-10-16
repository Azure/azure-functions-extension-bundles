# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Connector Poll integration tests with local HTTPS and identity emulators."""

import json
import os
import time
import uuid
from contextlib import ExitStack
from unittest.mock import patch

from tests.emulator_tests.utils.connector.connector_test_utils import ConnectorEmulator
from tests.utils import testutils


class TestConnectorPollFunctions(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'connector_poll_functions'

    @classmethod
    def setUpClass(cls):
        cls._resources = ExitStack()
        try:
            cls.emulator = cls._resources.enter_context(ConnectorEmulator())
            cls._resources.enter_context(patch.dict(
                os.environ, cls.emulator.environment))
            super().setUpClass()
        except BaseException:
            cls._resources.close()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls._resources.close()

    def setUp(self):
        self.emulator.post('/reset')

    def _wait_acknowledged(self, event):
        return self.emulator.wait_for(lambda state: any(
            item['id'] == event.message_id and item['acknowledged']
            for item in state['messages']))

    def _assert_poll_output(self, event):
        response = self.webhost.request('GET', 'get_connector_poll')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), event.payload)

    @staticmethod
    def _first_received_lock(state, event):
        return next(
            lock['lockToken']
            for call in state['calls'] if call['operation'] == 'receive'
            for lock in call.get('messages', [])
            if lock['messageId'] == event.message_id)

    def test_poll_delivery_and_acknowledgement(self):
        event = self.emulator.enqueue()
        self.assertNotEqual(event.message_id, event.payload['id'])
        state = self._wait_acknowledged(event)
        self._assert_poll_output(event)
        self.assertTrue(state['token_requests'])
        self.assertEqual(set(state['token_requests']), {'https://apihub.azure.com'})
        message = state['messages'][0]
        acknowledgements = [
            call for call in state['calls'] if call['operation'] == 'acknowledge'
        ]
        self.assertEqual(acknowledgements, [{
            'operation': 'acknowledge', 'trigger_config': 'poll',
            'status': 200, 'pending': False,
            'messages': [{
                'messageId': event.message_id, 'lockToken': message['lock_token']
            }],
        }])

    def test_poll_failed_invocation_is_redelivered_without_acknowledgement(self):
        event = self.emulator.enqueue(failures=1)
        state = self.emulator.wait_for(lambda state: any(
            item['body_finished'] and item['body_succeeded'] is False
            for item in state['invocations']))
        first_lock = self._first_received_lock(state, event)
        self.emulator.expire(event, first_lock)
        state = self._wait_acknowledged(event)
        self._assert_poll_output(event)
        self.assertGreaterEqual(state['messages'][0]['attempts'], 2)
        self.assertNotEqual(state['messages'][0]['lock_token'], first_lock)
        self.assertFalse(any(
            lock['lockToken'] == first_lock
            for call in state['calls'] if call['operation'] == 'acknowledge'
            for lock in call['messages']))
        self.assertTrue(any(
            item['message_id'] == event.message_id
            and item['body_succeeded'] is True
            for item in state['invocations']))

    def test_poll_and_webhook_coexist_without_cross_routing(self):
        event = self.emulator.enqueue()
        webhook_payload = {'id': str(uuid.uuid4()), 'source': 'webhook'}
        response = self.webhost.request(
            'POST',
            'runtime/webhooks/connector?functionName=connector_trigger_webhook',
            data=json.dumps(webhook_payload),
            headers={'Content-Type': 'application/json'},
            no_prefix=True)
        self.assertEqual(response.status_code, 202)
        result = self.webhost.request('GET', 'get_connector_webhook')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), webhook_payload)
        state = self._wait_acknowledged(event)
        self._assert_poll_output(event)
        self.assertTrue(all(
            item['message_id'] == event.message_id for item in state['invocations']))
        response = self.webhost.request(
            'POST',
            'runtime/webhooks/connector?functionName=connector_trigger_poll',
            data=json.dumps(webhook_payload),
            headers={'Content-Type': 'application/json'},
            no_prefix=True)
        self.assertEqual(response.status_code, 404)

    def test_poll_empty_queue_then_delivery(self):
        state = self.emulator.wait_for(lambda state: sum(
            call['operation'] == 'receive' and call['trigger_config'] == 'poll'
            and call.get('message_ids') == []
            for call in state['calls']) >= 2)
        self.assertEqual(state['invocations'], [])
        event = self.emulator.enqueue()
        self._wait_acknowledged(event)
        self._assert_poll_output(event)

    def test_poll_recovers_from_transient_receive_failures(self):
        self.emulator.post('/faults', {'receive': 2})
        event = self.emulator.enqueue()
        state = self._wait_acknowledged(event)
        self._assert_poll_output(event)
        failures = [
            call for call in state['calls']
            if call['operation'] == 'receive' and call['trigger_config'] == 'poll'
            and call['status'] == 503
        ]
        self.assertEqual(len(failures), 2)

    def test_poll_acknowledgement_failure_does_not_lose_message(self):
        self.emulator.post('/faults', {'acknowledge': 1})
        event = self.emulator.enqueue()
        state = self.emulator.wait_for(lambda state: any(
            call['operation'] == 'acknowledge' and call['status'] == 503
            and any(lock['messageId'] == event.message_id
                    for lock in call['messages'])
            for call in state['calls']))
        self.emulator.expire(event, self._first_received_lock(state, event))
        state = self._wait_acknowledged(event)
        self._assert_poll_output(event)
        statuses = [
            call['status'] for call in state['calls']
            if call['operation'] == 'acknowledge'
        ]
        self.assertEqual(statuses[0], 503)
        self.assertEqual(statuses[-1], 200)

    @staticmethod
    def _concurrency_receives(state):
        return [
            call for call in state['calls']
            if call['operation'] == 'receive'
            and call['trigger_config'] == 'concurrency'
        ]

    def _assert_capacity_held(self, receive_count, active_bodies):
        time.sleep(1.5)
        state = self.emulator.snapshot()
        self.assertEqual(state['active_bodies'], active_bodies)
        self.assertEqual(len(state['invocations']), 2)
        self.assertEqual(len(self._concurrency_receives(state)), receive_count)
        return state

    def test_poll_respects_single_event_concurrency_limit(self):
        events = []
        try:
            events = self.emulator.enqueue_many(
                4, blocked=True, trigger_config='concurrency',
                block_acknowledgement=True)
            state = self.emulator.wait_for(
                lambda state: state['active_bodies'] == 2)
            self.assertEqual(len(state['invocations']), 2)
            received = [
                call for call in self._concurrency_receives(state)
                if call['message_ids']
            ]
            self.assertEqual(received[0]['max_events'], 2)
            self.assertTrue(received[0]['more_messages_available'])
            receive_count = len(self._concurrency_receives(state))
            state = self._assert_capacity_held(receive_count, active_bodies=2)
            first_message_id = state['invocations'][0]['message_id']
            self.emulator.post('/release', {
                'message_id': first_message_id
            })
            self.emulator.wait_for(lambda state: any(
                call['operation'] == 'acknowledge' and call['pending']
                and any(lock['messageId'] == first_message_id
                        for lock in call['messages'])
                for call in state['calls']), timeout=10)
            self._assert_capacity_held(receive_count, active_bodies=1)
            self.emulator.post('/release_acknowledgements', {
                'message_id': first_message_id
            })
            state = self.emulator.wait_for(
                lambda state: len(state['invocations']) >= 3)
            self.assertEqual(len(state['invocations']), 3)
            next_receive = self._concurrency_receives(state)[receive_count]
            self.assertEqual(next_receive['max_events'], 1)
            self.assertEqual(len(next_receive['message_ids']), 1)
            self.assertEqual(state['active_bodies'], 2)
            self.assertLessEqual(state['peak_active_bodies'], 2)
        finally:
            try:
                self.emulator.post('/release')
            finally:
                self.emulator.post('/release_acknowledgements')
        for event in events:
            state = self._wait_acknowledged(event)
        self.assertEqual(len(state['invocations']), 4)
        self.assertLessEqual(state['peak_active_bodies'], 2)
