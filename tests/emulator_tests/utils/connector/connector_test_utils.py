# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Lifecycle and client helpers for the local Connector Poll emulator."""

import datetime
import ipaddress
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import ExitStack
from dataclasses import dataclass

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from tests.utils import testutils

from .emulator import CONTROL_HEADER


def _create_certificates(directory):
    now = datetime.datetime.now(datetime.timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(
        NameOID.COMMON_NAME, f'Connector emulator {uuid.uuid4()}')])
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name).issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(root_key, hashes.SHA256())
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
        .issuer_name(root_name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=2))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName('localhost'),
            x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
        ]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([
            ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    (directory / 'ca.pem').write_bytes(root.public_bytes(serialization.Encoding.PEM))
    (directory / 'ca.cer').write_bytes(root.public_bytes(serialization.Encoding.DER))
    (directory / 'cert.pem').write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM))
    key_path = directory / 'key.pem'
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    key_path.chmod(0o600)
    return root.fingerprint(hashes.SHA1()).hex().upper()


@dataclass(frozen=True)
class PollEvent:
    message_id: str
    payload: dict[str, str]


class ConnectorEmulator:
    def __enter__(self):
        self._resources = ExitStack()
        try:
            self.directory = pathlib.Path(self._resources.enter_context(
                tempfile.TemporaryDirectory(prefix='connector-emulator-')))
            thumbprint = _create_certificates(self.directory)
            self.control_token = str(uuid.uuid4())
            port = testutils._find_open_port()
            self.url = f'http://127.0.0.1:{port}'
            self.session = self._resources.enter_context(requests.Session())
            self.session.trust_env = False
            self.session.headers[CONTROL_HEADER] = self.control_token
            self.environment = {
                'ConnectorEmulator__pollingEndpoint':
                    'https://localhost/api/connectorGateways/emulator',
                'ConnectorEmulator__credential': 'managedidentity',
                'CONNECTOR_EMULATOR_URL': self.url,
                'CONNECTOR_EMULATOR_CONTROL_TOKEN': self.control_token,
                'IDENTITY_ENDPOINT': self.url + '/identity',
                'IDENTITY_HEADER': self.control_token,
                'SSL_CERT_FILE': str(self.directory / 'ca.pem'),
                'AzureFunctionsJobHost__extensions__connector__maxPollingInterval':
                    '00:00:01',
                'NO_PROXY': ','.join(filter(None, [
                    os.environ.get('NO_PROXY'), '127.0.0.1', 'localhost'
                ])),
            }
            script = pathlib.Path(__file__).with_name('emulator.py')
            if platform.system() == 'Windows':
                if os.environ.get('CONNECTOR_EMULATOR_TRUST_LOCAL_CERTIFICATE') != '1':
                    raise RuntimeError(
                        'Set CONNECTOR_EMULATOR_TRUST_LOCAL_CERTIFICATE=1 to allow '
                        'temporary current-user certificate trust for this test run.')
                self._update_windows_trust(
                    '-addstore', str(self.directory / 'ca.cer'))
                self._resources.callback(
                    self._update_windows_trust, '-delstore', thumbprint)
                log = self._resources.enter_context(
                    (self.directory / 'emulator.log').open('w+'))
                process = subprocess.Popen(
                    [sys.executable, str(script),
                     '--cert', str(self.directory / 'cert.pem'),
                     '--key', str(self.directory / 'key.pem'),
                     '--control-port', str(port)],
                    env={**os.environ,
                         'CONNECTOR_EMULATOR_CONTROL_TOKEN': self.control_token},
                    stdout=log, stderr=subprocess.STDOUT)
                self._resources.callback(
                    self._archive_log, self.directory / 'emulator.log')
                self._resources.callback(self._stop_process, process)
            elif platform.system() == 'Linux':
                config_path = self.directory / 'compose.json'
                config_path.write_text(json.dumps({
                    'services': {
                        'connector': {
                            'image': 'mcr.microsoft.com/azure-functions/python:4-python3.12',
                            'entrypoint': ['python'],
                            'ports': [
                                '127.0.0.1:443:443',
                                f'127.0.0.1:{port}:8080',
                            ],
                            'volumes': [
                                {
                                    'type': 'bind', 'source': str(script.parent),
                                    'target': '/emulator', 'read_only': True,
                                },
                                {
                                    'type': 'bind', 'source': str(self.directory),
                                    'target': '/certs', 'read_only': True,
                                },
                            ],
                            'environment': {
                                'CONNECTOR_EMULATOR_CONTROL_TOKEN': self.control_token,
                            },
                            'command': [
                                '/emulator/emulator.py',
                                '--cert', '/certs/cert.pem',
                                '--key', '/certs/key.pem',
                                '--control-port', '8080', '--bind', '0.0.0.0',
                            ],
                        },
                    },
                }), encoding='utf-8')
                command = [
                    'docker', 'compose',
                    '--project-name', f'connector-emulator-{uuid.uuid4().hex}',
                    '--file', str(config_path),
                ]
                log_path = self.directory / 'emulator.log'
                log_path.touch()
                self._resources.callback(
                    self._archive_log, log_path)
                self._resources.callback(
                    self._stop_compose_project, command, log_path)
                result = subprocess.run(
                    command + ['up', '--detach'],
                    capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(
                        'Connector emulator container failed to start:\n'
                        + result.stdout + result.stderr)
            else:
                raise RuntimeError('Connector Poll emulator supports Windows and Linux.')
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if platform.system() == 'Windows' and process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(
                        f'Connector Poll emulator exited during startup:\n{log.read()}')
                try:
                    response = self.session.get(self.url + '/health', timeout=2)
                    response.raise_for_status()
                    return self
                except (requests.ConnectionError, requests.Timeout):
                    time.sleep(0.1)
            raise TimeoutError('Connector Poll emulator did not start on localhost:443.')
        except BaseException as error:
            self._close_resources(error)
            raise

    def __exit__(self, exc_type, error, traceback):
        self._close_resources(error)

    def _close_resources(self, error=None):
        try:
            self._resources.close()
        except BaseException as cleanup_error:
            if error is not None:
                raise BaseExceptionGroup(
                    'Connector emulator failed and cleanup also failed',
                    [error, cleanup_error]) from None
            raise

    @staticmethod
    def _update_windows_trust(operation, certificate):
        executable = shutil.which('certutil')
        if executable is None:
            raise RuntimeError('certutil is required for temporary Windows TLS trust.')
        result = subprocess.run(
            [executable, '-user', '-f', operation, 'Root', certificate],
            capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(
                'Temporary Connector certificate trust operation failed:\n'
                + result.stdout + result.stderr)

    @staticmethod
    def _stop_process(process):
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    @staticmethod
    def _stop_compose_project(command, log_path):
        errors = []
        try:
            result = subprocess.run(
                command + ['logs', '--no-color'],
                capture_output=True, text=True)
            log_path.write_text(result.stdout + result.stderr, encoding='utf-8')
            if result.returncode:
                errors.append('Cannot collect emulator logs:\n'
                              + result.stdout + result.stderr)
        finally:
            result = subprocess.run(
                command + ['down', '--timeout', '5'],
                capture_output=True, text=True)
            if result.returncode:
                errors.append('Cannot stop the emulator Compose project:\n'
                              + result.stdout + result.stderr)
        if errors:
            raise RuntimeError('\n'.join(errors))

    @staticmethod
    def _archive_log(path):
        destination = testutils.TESTS_ROOT / 'logs' / 'connector-emulator.log'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)

    def post(self, path, body=None):
        response = self.session.post(
            self.url + path, json={} if body is None else body, timeout=5)
        response.raise_for_status()
        return response.json()

    def snapshot(self):
        response = self.session.get(self.url + '/state', timeout=5)
        response.raise_for_status()
        return response.json()

    def enqueue(self, **options):
        return self.enqueue_many(1, **options)[0]

    def expire(self, event, lock_token):
        self.post('/expire', {
            'message_id': event.message_id, 'lock_token': lock_token
        })

    def enqueue_many(self, count, *, failures=0, blocked=False, lease_seconds=180,
                     trigger_config='poll', block_acknowledgement=False):
        events = [
            PollEvent(
                message_id=str(uuid.uuid4()),
                payload={'id': str(uuid.uuid4()), 'source': 'connector-emulator'})
            for _ in range(count)
        ]
        self.post('/enqueue', {
            'messages': [
                {
                    'message_id': event.message_id, 'payload': event.payload,
                    'failures': failures, 'blocked': blocked,
                    'lease_seconds': lease_seconds,
                    'trigger_config': trigger_config,
                    'block_acknowledgement': block_acknowledgement,
                }
                for event in events
            ],
        })
        return events

    def wait_for(self, predicate, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.snapshot()
            if predicate(state):
                return state
            time.sleep(0.1)
        raise AssertionError(
            f'Connector emulator condition timed out. State: {self.snapshot()}')
