# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Protocol and lifecycle checks for the Connector test infrastructure."""

import errno
import json
import socket
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from tests.emulator_tests.utils.connector.connector_test_utils import ConnectorEmulator
from tests.emulator_tests.utils.connector.emulator import (
    ACCESS_TOKEN,
    CONTROL_HEADER,
    POLL_PATH,
    EmulatorServer,
    Handler,
    State,
)
from tests.utils import testutils


@pytest.fixture
def protocol():
    state = State()
    token = 'local-protocol-test'
    control = EmulatorServer(('127.0.0.1', 0), Handler)
    runtime = EmulatorServer(('127.0.0.1', 0), Handler)
    threads = []
    for server, is_runtime in ((control, False), (runtime, True)):
        server.state = state
        server.runtime = is_runtime
        server.control_token = token
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
    control_session = requests.Session()
    control_session.trust_env = False
    control_session.headers[CONTROL_HEADER] = token
    runtime_session = requests.Session()
    runtime_session.trust_env = False
    runtime_session.headers['Authorization'] = f'Bearer {ACCESS_TOKEN}'
    emulator = ConnectorEmulator()
    emulator.url = f'http://127.0.0.1:{control.server_port}'
    emulator.session = control_session
    emulator.control_token = token
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        yield SimpleNamespace(
            emulator=emulator, state=state, runtime=runtime_session,
            url=f'http://127.0.0.1:{runtime.server_port}', executor=executor)
    finally:
        with state.condition:
            for item in state.messages.values():
                item['blocked'] = False
                item['acknowledgement_blocked'] = False
            state.condition.notify_all()
        executor.shutdown(wait=True)
        control_session.close()
        runtime_session.close()
        for server in (control, runtime):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


def _receive(protocol, maximum=1, trigger_config='poll'):
    response = protocol.runtime.get(
        protocol.url + POLL_PATH + trigger_config + '/receive',
        params={'maxEvents': maximum}, timeout=5)
    response.raise_for_status()
    return response


def _acknowledge(protocol, message_id, lock_token, trigger_config='poll'):
    response = protocol.runtime.post(
        protocol.url + POLL_PATH + trigger_config + '/acknowledge',
        json={'messages': [{
            'messageId': message_id, 'lockToken': lock_token,
        }]}, timeout=5)
    return response


def test_acknowledgement_uses_transport_id_not_payload_id(protocol):
    event = protocol.emulator.enqueue()
    message = _receive(protocol).json()['messages'][0]
    assert message['messageId'] == event.message_id
    assert message['outputs'] == event.payload
    assert message['messageId'] != message['outputs']['id']

    wrong = _acknowledge(protocol, event.payload['id'], message['lockToken'])
    assert wrong.status_code == 200
    assert wrong.json()['results'][0]['status'] == 'NotFound'
    assert not protocol.emulator.snapshot()['messages'][0]['acknowledged']

    correct = _acknowledge(protocol, event.message_id, message['lockToken'])
    assert correct.status_code == 200
    assert correct.json()['results'][0]['status'] == 'Acknowledged'
    assert protocol.emulator.snapshot()['messages'][0]['acknowledged']


def test_explicit_expiry_preserves_received_locks_and_rejects_stale_control(protocol):
    event = protocol.emulator.enqueue()
    first = _receive(protocol).json()['messages'][0]
    original_record = protocol.emulator.snapshot()['calls'][0]['messages'][0]
    protocol.emulator.expire(event, first['lockToken'])
    second = _receive(protocol).json()['messages'][0]
    assert second['messageId'] == first['messageId'] == event.message_id
    assert second['lockToken'] != first['lockToken']
    assert second['outputs'] == first['outputs'] == event.payload
    assert protocol.emulator.snapshot()['calls'][0]['messages'][0] == original_record
    with pytest.raises(requests.HTTPError) as stale_expiry:
        protocol.emulator.expire(event, first['lockToken'])
    assert stale_expiry.value.response.status_code == 409
    stale = _acknowledge(protocol, event.message_id, first['lockToken'])
    assert stale.json()['results'][0]['status'] == 'NotFound'
    current = _acknowledge(protocol, event.message_id, second['lockToken'])
    assert current.json()['results'][0]['status'] == 'Acknowledged'


def test_receive_respects_requested_capacity_and_reports_backlog(protocol):
    events = protocol.emulator.enqueue_many(4, trigger_config='concurrency')
    first = _receive(protocol, maximum=2, trigger_config='concurrency')
    assert len(first.json()['messages']) == 2
    assert first.headers['x-ms-more-messages-available'] == 'true'
    second = _receive(protocol, maximum=1, trigger_config='concurrency')
    assert len(second.json()['messages']) == 1
    assert second.headers['x-ms-more-messages-available'] == 'true'
    third = _receive(protocol, maximum=1, trigger_config='concurrency')
    assert len(third.json()['messages']) == 1
    assert third.headers['x-ms-more-messages-available'] == 'false'
    received = [
        message['messageId']
        for response in (first, second, third)
        for message in response.json()['messages']
    ]
    assert set(received) == {event.message_id for event in events}


def test_invocation_timeout_releases_body_bookkeeping(protocol):
    protocol.state.invocation_timeout = 0.02
    event = protocol.emulator.enqueue(blocked=True)
    _receive(protocol)
    with pytest.raises(requests.HTTPError) as error:
        protocol.emulator.post('/invocations/start', {
            'payload_id': event.payload['id']
        })
    assert error.value.response.status_code == 504
    state = protocol.emulator.snapshot()
    assert state['active_bodies'] == 0
    assert state['invocations'][0]['body_finished']
    assert state['invocations'][0]['body_succeeded'] is False
    assert state['invocations'][0]['error'] == 'Invocation release timed out'
    with pytest.raises(requests.HTTPError) as late_completion:
        protocol.emulator.post('/invocations/complete', {
            'invocation_id': state['invocations'][0]['id'],
            'body_succeeded': False,
        })
    assert late_completion.value.response.status_code == 409
    assert protocol.emulator.snapshot()['active_bodies'] == 0
    protocol.emulator.post('/reset')


@pytest.mark.parametrize('failures', [0, 1])
def test_function_body_reports_its_own_completion_not_acknowledgement(protocol, failures):
    from tests.emulator_tests.connector_poll_functions.function_app import _process_poll_event

    event = protocol.emulator.enqueue(failures=failures)
    _receive(protocol)
    with patch.dict('os.environ', {
        'CONNECTOR_EMULATOR_URL': protocol.emulator.url,
        'CONNECTOR_EMULATOR_CONTROL_TOKEN': protocol.emulator.control_token,
    }):
        if failures:
            with pytest.raises(RuntimeError, match='Intentional Connector'):
                _process_poll_event(json.dumps(event.payload))
        else:
            assert json.loads(_process_poll_event(json.dumps(event.payload))) == event.payload
    state = protocol.emulator.snapshot()
    assert state['active_bodies'] == 0
    assert state['invocations'][0]['message_id'] == event.message_id
    assert state['invocations'][0]['payload_id'] == event.payload['id']
    assert state['invocations'][0]['body_finished']
    assert state['invocations'][0]['body_succeeded'] is (failures == 0)
    assert not state['messages'][0]['acknowledged']


def test_acknowledgement_stays_pending_until_released(protocol):
    event = protocol.emulator.enqueue(block_acknowledgement=True)
    message = _receive(protocol).json()['messages'][0]
    future = protocol.executor.submit(
        _acknowledge, protocol, event.message_id, message['lockToken'])
    state = protocol.emulator.wait_for(lambda state: any(
        call.get('pending') for call in state['calls']), timeout=2)
    assert not future.done()
    assert not state['messages'][0]['acknowledged']
    with pytest.raises(requests.HTTPError) as reset:
        protocol.emulator.post('/reset')
    assert reset.value.response.status_code == 409
    protocol.emulator.post('/release_acknowledgements', {
        'message_id': event.message_id
    })
    response = future.result(timeout=5)
    assert response.status_code == 200
    assert response.json()['results'][0]['status'] == 'Acknowledged'
    state = protocol.emulator.snapshot()
    assert state['messages'][0]['acknowledged']
    assert not any(call.get('pending') for call in state['calls'])
    protocol.emulator.post('/reset')


def test_acknowledgement_timeout_clears_pending_without_deleting_message(protocol):
    protocol.state.acknowledgement_timeout = 0.02
    event = protocol.emulator.enqueue(block_acknowledgement=True)
    message = _receive(protocol).json()['messages'][0]
    response = _acknowledge(protocol, event.message_id, message['lockToken'])
    assert response.status_code == 504
    state = protocol.emulator.snapshot()
    assert not state['messages'][0]['acknowledged']
    assert not any(call.get('pending') for call in state['calls'])
    protocol.emulator.post('/reset')


@pytest.mark.parametrize('startup_failure', [None, 'bind', 'process'])
def test_compose_cleanup_is_registered_before_startup(startup_failure):
    commands = []
    archived = []

    def run(command, **kwargs):
        commands.append(command)
        if 'up' in command:
            config = json.loads(Path(
                command[command.index('--file') + 1]).read_text(encoding='utf-8'))
            assert config['services']['connector']['image'] == 'python:3.12-slim'
            if startup_failure == 'process':
                raise OSError('Docker process could not start')
            return subprocess.CompletedProcess(
                command, 1 if startup_failure == 'bind' else 0,
                '', 'Port 443 is occupied' if startup_failure == 'bind' else '')
        if 'logs' in command:
            return subprocess.CompletedProcess(command, 0, 'startup diagnostics', '')
        assert 'down' in command
        return subprocess.CompletedProcess(command, 0, '', '')

    ready = requests.Response()
    ready.status_code = 200
    with (
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'platform.system', return_value='Linux'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              '_create_certificates', return_value='test-thumbprint'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'subprocess.run', side_effect=run),
        patch.object(requests.Session, 'get', return_value=ready),
        patch.object(ConnectorEmulator, '_archive_log',
                     side_effect=lambda path: archived.append(path.read_text())),
    ):
        if startup_failure is None:
            with ConnectorEmulator():
                pass
        else:
            expected = OSError if startup_failure == 'process' else RuntimeError
            with pytest.raises(expected):
                with ConnectorEmulator():
                    pytest.fail('Failed startup must not enter the context')
    assert len(commands) == 3
    assert 'up' in commands[0]
    assert 'logs' in commands[1]
    assert 'down' in commands[2]
    assert commands[0][:-2] == commands[1][:-2] == commands[2][:-3]
    assert archived == ['startup diagnostics']


def test_startup_error_is_preserved_when_compose_cleanup_also_fails():
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if 'up' in command:
            return subprocess.CompletedProcess(command, 1, '', 'Startup failed')
        if 'logs' in command:
            return subprocess.CompletedProcess(command, 1, '', 'Logs failed')
        return subprocess.CompletedProcess(command, 1, '', 'Shutdown failed')

    with (
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'platform.system', return_value='Linux'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              '_create_certificates', return_value='test-thumbprint'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'subprocess.run', side_effect=run),
        patch.object(ConnectorEmulator, '_archive_log'),
        pytest.raises(BaseExceptionGroup) as error,
    ):
        with ConnectorEmulator():
            pytest.fail('Failed startup must not enter the context')
    assert 'Startup failed' in str(error.value.exceptions[0])
    assert 'Logs failed' in str(error.value.exceptions[1])
    assert 'Shutdown failed' in str(error.value.exceptions[1])
    assert 'down' in commands[-1]


@pytest.mark.parametrize('source', ['environment', 'worker_config'])
def test_webhost_diagnostics_omit_credentials(source, tmp_path, caplog, capsys):
    executable = tmp_path / 'func'
    executable.write_text('', encoding='utf-8')
    executable.chmod(0o700)
    config_marker = 'synthetic-configuration-value-not-a-credential'
    (tmp_path / 'host.json').write_text(json.dumps({
        'version': '2.0',
        'extensions': {'testOnlyDiagnosticSetting': config_marker},
    }), encoding='utf-8')
    worker_config = tmp_path / 'worker.config.ini'
    environment = {'CORE_TOOLS_EXE_PATH': str(executable)}
    if source == 'environment':
        expected = {
            'AzureWebJobsStorage': 'synthetic-storage-value-not-a-credential',
            'MySqlConnectionString': 'synthetic-mysql-value-not-a-credential',
            'AzureSignalRConnectionString': 'synthetic-signalr-value-not-a-credential',
            'RabbitMQConnectionString': 'synthetic-rabbitmq-value-not-a-credential',
            'FUNCTIONS_EXTENSIONBUNDLE_SOURCE_URI':
                'https://example.invalid/bundles?sig=synthetic-test-value',
        }
        environment.update(expected)
    else:
        worker_config.write_text(
            '[azure]\n'
            'storage_key = synthetic-worker-storage-value-not-a-credential\n'
            'servicebus_key = synthetic-worker-servicebus-value-not-a-credential\n',
            encoding='utf-8')
        expected = {
            'AzureWebJobsStorageConnectionString':
                'synthetic-worker-storage-value-not-a-credential',
            'AzureWebJobsServicebusConnectionString':
                'synthetic-worker-servicebus-value-not-a-credential',
        }
    with (
        patch.dict('os.environ', environment, clear=True),
        patch.object(testutils, 'WORKER_CONFIG', worker_config),
        patch.object(testutils.subprocess, 'Popen') as popen,
        caplog.at_level('DEBUG'),
    ):
        testutils.popen_webhost(
            script_root=tmp_path, stdout=None, stderr=None, port=7071)
    captured = capsys.readouterr()
    diagnostic = (tmp_path / 'webhost_config.txt').read_text()
    published_text = caplog.text + captured.out + captured.err + diagnostic
    for name, value in expected.items():
        assert name in diagnostic
        assert value not in published_text
        assert popen.call_args.kwargs['env'][name] == value
    assert config_marker not in published_text


@pytest.mark.parametrize('failure', ['timeout', 'interrupted', 'already_exited'])
def test_webhost_startup_failure_stops_and_reaps_owned_process(failure):
    process = Mock(stdout=None, stderr=None)
    process.poll.return_value = 0 if failure == 'already_exited' else None
    health = KeyboardInterrupt('Synthetic startup cancellation') if (
        failure == 'interrupted') else None
    expected = KeyboardInterrupt if health is not None else RuntimeError
    with (
        patch.object(testutils, 'popen_webhost', return_value=process),
        patch.object(testutils, '_find_webhost_port', return_value=7071),
        patch.object(testutils._WebHostProxy, 'is_healthy',
                     side_effect=health, return_value=False),
        patch.object(testutils.time, 'sleep'),
        pytest.raises(expected),
    ):
        testutils.start_webhost(
            script_dir=Path('startup-regression'), stdout=subprocess.DEVNULL)
    if failure == 'already_exited':
        process.terminate.assert_not_called()
    else:
        process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(20)


def test_webhost_success_leaves_process_owned_by_returned_proxy():
    process = Mock(stdout=None, stderr=None)
    process.poll.return_value = None
    with (
        patch.object(testutils, 'popen_webhost', return_value=process),
        patch.object(testutils, '_find_webhost_port', return_value=7071),
        patch.object(testutils._WebHostProxy, 'is_healthy', return_value=True),
    ):
        proxy = testutils.start_webhost(
            script_dir=Path('startup-regression'), stdout=subprocess.DEVNULL)
    process.terminate.assert_not_called()
    process.wait.assert_not_called()
    proxy.close()
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(20)


def test_webhost_http_port_is_outside_default_ephemeral_range():
    port = testutils._find_webhost_port()
    assert 15000 <= port < 25000
    with socket.socket() as candidate:
        candidate.bind((testutils.LOCALHOST, port))


def test_webhost_http_port_skips_an_occupied_listener():
    with socket.socket() as occupied:
        occupied.bind((testutils.LOCALHOST, 0))
        occupied.listen(1)
        occupied_port = occupied.getsockname()[1]
        with socket.socket() as available:
            available.bind((testutils.LOCALHOST, 0))
            available_port = available.getsockname()[1]
        with patch.object(
                testutils.random.SystemRandom, 'sample',
                return_value=[occupied_port, available_port]):
            assert testutils._find_webhost_port() == available_port


def test_webhost_http_port_exhaustion_is_reported():
    candidate = Mock()
    candidate.__enter__ = Mock(return_value=candidate)
    candidate.__exit__ = Mock(return_value=False)
    candidate.bind.side_effect = OSError(errno.EADDRINUSE, 'Synthetic port conflict')
    with (
        patch.object(testutils.socket, 'socket', return_value=candidate),
        pytest.raises(RuntimeError, match='No HTTP test port was available'),
    ):
        testutils._find_webhost_port()
    assert candidate.bind.call_count == 100
