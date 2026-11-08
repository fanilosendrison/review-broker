"""Status-bearing REST wire responses for injected journal transports."""
import json
import subprocess


def http_response(command, value, status=200, code=None):
    body = json.dumps(value)
    if '--include' in command:
        body = f'HTTP/2.0 {status} Fixture\r\nContent-Type: application/json\r\n\r\n' + body
    return subprocess.CompletedProcess(command, (0 if status < 400 else 1) if code is None else code, body, '')


def scoped_response(command, value, code=0):
    """Supply real REST ref identity omitted by the earlier body-only doubles."""
    endpoint = command[4]
    if isinstance(value, dict) and '/git/refs/heads/' in endpoint and 'object' in value:
        value = dict(value, ref='refs/heads/' + endpoint.split('/git/refs/heads/')[1],
                     url='https://api.github.com/' + endpoint)
        value['object'] = dict(value['object'], type='commit')
    status = 201 if command[3] == 'POST' else 200
    return http_response(command, value, status if not code else 422, code)
