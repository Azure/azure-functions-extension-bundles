# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Protocol and lifecycle checks for the Connector test infrastructure."""

import errno
import io
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
    STABLE_POLL_PATH,
    EmulatorServer,
    Handler,
    State,
)
from tests.utils import testutils


@pytest.mark.parametrize('function_name', [
    'get_connector_default', 'get_connector_explicit'
])
def test_webhook_readback_preserves_callback_envelope(function_name):
    import azure.functions as func
    from tests.emulator_tests.connector_functions import function_app

    payload = {
        'id': 'synthetic-correlation-id',
        'metadata': {'source': 'office365'},
        'body': {'value': [{'id': 'synthetic-message-id'}]},
    }
    function = getattr(function_app, function_name).build().get_user_function()
    response = function(
        func.HttpRequest(method='GET', url='http://localhost/api/readback', body=b''),
        io.BytesIO(json.dumps(payload).encode('utf-8')))
    assert isinstance(response, func.HttpResponse)
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert json.loads(response.get_body()) == payload


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


def test_emulator_process_serves_both_endpoint_forms_with_trusted_tls():
    processes = []
    popen = subprocess.Popen

    def start(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    # Exercise the cross-platform process/TLS path without importing a Windows CA.
    with (
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'platform.system', return_value='Linux'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'subprocess.Popen', side_effect=start),
        patch.object(ConnectorEmulator, '_update_windows_trust') as import_trust,
    ):
        with ConnectorEmulator() as emulator:
            directory = emulator.directory
            verify = str(directory / 'ca.pem')
            port = int(emulator.runtime_url.rsplit(':', 1)[1])
            assert 1024 < port <= 65535
            assert emulator.environment['ConnectorStableEmulator__pollingEndpoint'] == (
                emulator.runtime_url)
            assert emulator.environment['ConnectorEmulator__pollingEndpoint'] == (
                emulator.runtime_url + '/api/connectorGateways/emulator')
            for prefix, trigger_config in (
                    (STABLE_POLL_PATH, 'stable'), (POLL_PATH, 'poll')):
                event = emulator.enqueue(trigger_config=trigger_config)
                url = emulator.runtime_url + prefix + trigger_config
                headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
                received = emulator.session.get(
                    url + '/receive', params={'maxEvents': 1}, headers=headers,
                    verify=verify, timeout=5)
                received.raise_for_status()
                message = received.json()['messages'][0]
                assert message['messageId'] == event.message_id
                assert message['outputs'] == event.payload
                acknowledged = emulator.session.post(
                    url + '/acknowledge', json={'messages': [{
                        'messageId': message['messageId'],
                        'lockToken': message['lockToken'],
                    }]}, headers=headers, verify=verify, timeout=5)
                acknowledged.raise_for_status()
                assert acknowledged.json()['results'][0]['status'] == 'Acknowledged'
                wrong_prefix = (
                    POLL_PATH if prefix == STABLE_POLL_PATH else STABLE_POLL_PATH)
                wrong = emulator.session.get(
                    emulator.runtime_url + wrong_prefix + trigger_config + '/receive',
                    params={'maxEvents': 1}, headers=headers,
                    verify=verify, timeout=5)
                assert wrong.status_code == 404
        import_trust.assert_not_called()
    assert len(processes) == 1
    assert processes[0].poll() is not None
    assert not directory.exists()


def test_emulator_process_startup_failure_is_stopped_and_logged():
    process = Mock()
    process.poll.return_value = 1
    archived = []
    with (
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'platform.system', return_value='Linux'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'subprocess.Popen', return_value=process),
        patch.object(ConnectorEmulator, '_archive_log',
                     side_effect=lambda path: archived.append(path.exists())),
        pytest.raises(RuntimeError, match='exited during startup'),
    ):
        with ConnectorEmulator():
            pytest.fail('Failed startup must not enter the context')
    process.terminate.assert_not_called()
    process.wait.assert_called_once_with(timeout=10)
    assert archived == [True]


def test_startup_error_is_preserved_when_process_cleanup_also_fails():
    process = Mock()
    process.poll.return_value = 1
    process.wait.side_effect = OSError('Synthetic shutdown failure')
    with (
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'platform.system', return_value='Linux'),
        patch('tests.emulator_tests.utils.connector.connector_test_utils.'
              'subprocess.Popen', return_value=process),
        patch.object(ConnectorEmulator, '_archive_log'),
        pytest.raises(BaseExceptionGroup) as error,
    ):
        with ConnectorEmulator():
            pytest.fail('Failed startup must not enter the context')
    assert 'exited during startup' in str(error.value.exceptions[0])
    assert 'Synthetic shutdown failure' in str(error.value.exceptions[1])


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
