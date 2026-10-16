# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Local Connector Poll protocol and managed-identity emulator."""

import argparse
import json
import os
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


ACCESS_TOKEN = 'connector-emulator-access-token'
CONTROL_HEADER = 'x-connector-emulator'
POLL_PATH = '/api/connectorGateways/emulator/triggerConfigs/'


class EmulatorServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True
    tls_context = None

    def finish_request(self, request, client_address):
        if self.tls_context is None:
            super().finish_request(request, client_address)
        else:
            # A slow TLS handshake must not block accepting other Poll requests.
            request.settimeout(10)
            with self.tls_context.wrap_socket(
                    request, server_side=True) as connection:
                super().finish_request(connection, client_address)


class State:
    def __init__(self, invocation_timeout=120, acknowledgement_timeout=20):
        self.condition = threading.Condition()
        self.invocation_timeout = invocation_timeout
        self.acknowledgement_timeout = acknowledgement_timeout
        self.token_requests = []
        self.reset()

    def reset(self):
        self.messages = {}
        self.invocations = []
        self.calls = []
        self.active_bodies = 0
        self.peak_active_bodies = 0
        self.receive_failures = 0
        self.acknowledge_failures = 0

    def snapshot(self):
        return {
            'messages': list(self.messages.values()),
            'invocations': self.invocations,
            'calls': self.calls,
            'active_bodies': self.active_bodies,
            'peak_active_bodies': self.peak_active_bodies,
            'token_requests': self.token_requests,
        }

    def finish_invocation(self, invocation, succeeded, error=None):
        with self.condition:
            invocation['body_finished'] = True
            invocation['body_succeeded'] = succeeded
            invocation['error'] = error
            self.active_bodies -= 1
            self.condition.notify_all()

    def locked_message(self, trigger_config, lock):
        item = self.messages.get(lock['messageId'])
        if (item is not None and not item['acknowledged']
                and item['trigger_config'] == trigger_config
                and item['lock_token'] == lock['lockToken']
                and item['lease_until'] > time.monotonic()):
            return item
        return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_request(self, code='-', size='-'):
        if isinstance(code, int) and code >= 400:
            super().log_request(code, size)

    def respond(self, status, content, headers=None):
        body = json.dumps(content).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            body = bytearray()
            while True:
                size = int(self.rfile.readline().split(b';', 1)[0], 16)
                if size == 0:
                    while self.rfile.readline() not in (b'\r\n', b''):
                        pass
                    break
                chunk = self.rfile.read(size)
                if len(chunk) != size or self.rfile.read(2) != b'\r\n':
                    raise ValueError('Incomplete chunked request body')
                body.extend(chunk)
        else:
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        return json.loads(body)

    def runtime_route(self):
        path = urlsplit(self.path).path
        if path.startswith(POLL_PATH):
            segments = path[len(POLL_PATH):].split('/')
            if len(segments) == 2 and segments[0] in ('poll', 'concurrency'):
                return segments
        return None, None

    def do_GET(self):
        path = urlsplit(self.path)
        state = self.server.state
        with state.condition:
            if not self.server.runtime:
                if path.path == '/identity':
                    if self.headers.get('X-IDENTITY-HEADER') != self.server.control_token:
                        self.respond(403, {'error': 'Invalid identity header'})
                        return
                    query = parse_qs(path.query)
                    resource = query.get('resource', [''])[0]
                    state.token_requests.append(resource)
                    if resource != 'https://apihub.azure.com':
                        self.respond(400, {'error': 'Unexpected token resource'})
                        return
                    self.respond(200, {
                        'access_token': ACCESS_TOKEN,
                        'expires_on': str(int(time.time()) + 3600),
                        'expires_in': '3600',
                        'resource': resource,
                        'token_type': 'Bearer',
                    })
                    return
                if self.headers.get(CONTROL_HEADER) != self.server.control_token:
                    self.respond(403, {'error': 'Invalid control header'})
                    return
                if path.path == '/state':
                    self.respond(200, state.snapshot())
                elif path.path == '/health':
                    self.respond(200, {'ready': True})
                else:
                    self.respond(404, {'error': 'Unknown control endpoint'})
                return

            if self.headers.get('Authorization') != f'Bearer {ACCESS_TOKEN}':
                self.respond(401, {'error': 'Expected emulated identity token'})
                return
            trigger_config, operation = self.runtime_route()
            if operation == 'approximateQueueDepth':
                self.respond(200, {
                    'approximateQueueDepth': sum(
                        not item['acknowledged']
                        and item['trigger_config'] == trigger_config
                        for item in state.messages.values())
                })
                return
            if operation != 'receive':
                self.respond(404, {'error': 'Unknown Connector endpoint'})
                return
            maximum = int(parse_qs(path.query).get('maxEvents', ['0'])[0])
            if not 1 <= maximum <= 32:
                self.respond(400, {'error': 'Invalid maxEvents'})
                return
            call = {
                'operation': 'receive', 'trigger_config': trigger_config,
                'max_events': maximum, 'status': 200,
            }
            state.calls.append(call)
            if trigger_config == 'poll' and state.receive_failures:
                state.receive_failures -= 1
                call['status'] = 503
                self.respond(503, {'error': 'Injected Receive failure'})
                return
            messages = []
            for item in state.messages.values():
                if (item['trigger_config'] != trigger_config
                        or item['acknowledged']
                        or item['lease_until'] > time.monotonic()):
                    continue
                item['attempts'] += 1
                item['lock_token'] = str(uuid.uuid4())
                item['lease_until'] = time.monotonic() + item['lease_seconds']
                messages.append({
                    'messageId': item['id'],
                    'lockToken': item['lock_token'],
                    'outputs': item['payload'],
                })
                if len(messages) == maximum:
                    break
            call['message_ids'] = [item['messageId'] for item in messages]
            call['messages'] = [
                {'messageId': item['messageId'], 'lockToken': item['lockToken']}
                for item in messages
            ]
            more_available = any(
                item['trigger_config'] == trigger_config
                and not item['acknowledged']
                and item['lease_until'] <= time.monotonic()
                for item in state.messages.values())
            call['more_messages_available'] = more_available
            self.respond(200, {'messages': messages}, {
                'x-ms-more-messages-available': str(more_available).lower()
            })

    def do_POST(self):
        path = urlsplit(self.path).path
        state = self.server.state
        try:
            body = self.read_json()
        except ValueError as error:
            self.log_error('Invalid JSON request: %s', error)
            self.respond(400, {'error': 'Invalid JSON request body'})
            return
        with state.condition:
            if self.server.runtime:
                if self.headers.get('Authorization') != f'Bearer {ACCESS_TOKEN}':
                    self.respond(401, {'error': 'Expected emulated identity token'})
                    return
                trigger_config, operation = self.runtime_route()
                if operation != 'acknowledge':
                    self.respond(404, {'error': 'Unknown Connector endpoint'})
                    return
                locks = body['messages']
                call = {
                    'operation': 'acknowledge', 'trigger_config': trigger_config,
                    'messages': locks, 'status': None, 'pending': True,
                }
                state.calls.append(call)
                if trigger_config == 'poll' and state.acknowledge_failures:
                    state.acknowledge_failures -= 1
                    call['status'] = 503
                    call['pending'] = False
                    self.respond(503, {'error': 'Injected Acknowledge failure'})
                    return
                leased = [
                    item for lock in locks
                    if (item := state.locked_message(trigger_config, lock)) is not None
                ]
                try:
                    released = state.condition.wait_for(
                        lambda: all(not item['acknowledgement_blocked']
                                    for item in leased),
                        timeout=state.acknowledgement_timeout)
                    if not released:
                        call['status'] = 504
                        self.respond(504, {
                            'error': 'Acknowledgement was not released'
                        })
                        return
                finally:
                    call['pending'] = False
                    state.condition.notify_all()
                call['status'] = 200
                results = []
                for lock in locks:
                    item = state.locked_message(trigger_config, lock)
                    if item is not None:
                        item['acknowledged'] = True
                    results.append({
                        'messageId': lock['messageId'],
                        'status': 'Acknowledged' if item is not None else 'NotFound',
                    })
                self.respond(200, {'results': results})
                return

            if self.headers.get(CONTROL_HEADER) != self.server.control_token:
                self.respond(403, {'error': 'Invalid control header'})
                return
            if path == '/reset':
                if (state.active_bodies
                        or any(call.get('pending') for call in state.calls)):
                    self.respond(409, {'error': 'Processing is still active'})
                    return
                state.reset()
            elif path == '/enqueue':
                for message in body['messages']:
                    message_id = message['message_id']
                    state.messages[message_id] = {
                        'id': message_id, 'payload': message['payload'],
                        'trigger_config': message.get('trigger_config', 'poll'),
                        'failures_remaining': message.get('failures', 0),
                        'blocked': message.get('blocked', False),
                        'acknowledgement_blocked':
                            message.get('block_acknowledgement', False),
                        'lease_seconds': message.get('lease_seconds', 180),
                        'lease_until': 0, 'lock_token': None,
                        'attempts': 0, 'acknowledged': False,
                    }
            elif path == '/faults':
                state.receive_failures = body.get('receive', 0)
                state.acknowledge_failures = body.get('acknowledge', 0)
            elif path == '/expire':
                item = state.messages.get(body['message_id'])
                if item is None:
                    self.respond(404, {'error': 'Unknown delivery ID'})
                    return
                if (item['acknowledged'] or item['lock_token'] is None
                        or item['lock_token'] != body['lock_token']):
                    self.respond(409, {'error': 'Delivery lock is no longer current'})
                    return
                item['lease_until'] = 0
                state.calls.append({
                    'operation': 'expire', 'message_id': item['id'],
                    'lock_token': body['lock_token'],
                })
                state.condition.notify_all()
            elif path == '/release':
                for item in state.messages.values():
                    if body.get('message_id') in (None, item['id']):
                        item['blocked'] = False
                state.condition.notify_all()
            elif path == '/release_acknowledgements':
                for item in state.messages.values():
                    if body.get('message_id') in (None, item['id']):
                        item['acknowledgement_blocked'] = False
                state.condition.notify_all()
            elif path == '/invocations/start':
                item = next((
                    item for item in state.messages.values()
                    if item['payload']['id'] == body['payload_id']
                ), None)
                if item is None:
                    self.respond(404, {'error': 'Unknown payload correlation ID'})
                    return
                failed = item['failures_remaining'] > 0
                if failed:
                    item['failures_remaining'] -= 1
                invocation = {
                    'id': str(uuid.uuid4()), 'message_id': item['id'],
                    'payload_id': body['payload_id'],
                    'body_finished': False, 'body_succeeded': None, 'error': None,
                }
                state.invocations.append(invocation)
                state.active_bodies += 1
                state.peak_active_bodies = max(
                    state.peak_active_bodies, state.active_bodies)
                if not state.condition.wait_for(
                        lambda: not item['blocked'],
                        timeout=state.invocation_timeout):
                    state.finish_invocation(
                        invocation, False, 'Invocation release timed out')
                    self.respond(504, {'error': 'Invocation was not released'})
                    return
                try:
                    self.respond(200, {
                        'invocation_id': invocation['id'], 'fail': failed
                    })
                except OSError:
                    state.finish_invocation(
                        invocation, False, 'Invocation response could not be delivered')
                    raise
                return
            elif path == '/invocations/complete':
                invocation = next((
                    item for item in state.invocations
                    if item['id'] == body['invocation_id']
                    and not item['body_finished']
                ), None)
                if invocation is None:
                    self.respond(409, {'error': 'Invocation is not active'})
                    return
                state.finish_invocation(invocation, body['body_succeeded'])
            else:
                self.respond(404, {'error': 'Unknown control endpoint'})
                return
            self.respond(200, {'ok': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cert', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--control-port', required=True, type=int)
    parser.add_argument('--bind', default='127.0.0.1')
    args = parser.parse_args()
    state = State()
    runtime = EmulatorServer((args.bind, 443), Handler)
    control = EmulatorServer((args.bind, args.control_port), Handler)
    for server, is_runtime in ((runtime, True), (control, False)):
        server.state = state
        server.runtime = is_runtime
        server.control_token = os.environ['CONNECTOR_EMULATOR_CONTROL_TOKEN']
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(args.cert, args.key)
    runtime.tls_context = tls
    threading.Thread(target=runtime.serve_forever, daemon=True).start()
    try:
        control.serve_forever()
    finally:
        runtime.shutdown()
        runtime.server_close()
        control.server_close()


if __name__ == '__main__':
    main()
