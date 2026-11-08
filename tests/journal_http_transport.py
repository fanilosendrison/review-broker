"""Instrumented GitHub HTTP fixture backed only by disposable local Git."""
import json

from tests.journal_git_transport import JournalGitTransport
from tests.journal_http_response import http_response, scoped_response


class HttpGitTransport(JournalGitTransport):
    def __init__(self, root):
        super().__init__(root)
        self.calls = []
        self.fault = None
        self.after_create = None
        self.before_create = None
        base = self.commit(self.base_tree, [], 'base')
        self.git('update-ref', 'refs/heads/dev', base)

    def objects(self):
        return sorted(str(p.relative_to(self.root)) for p in (self.root / 'objects').glob('*/*') if p.is_file())

    def refs(self):
        return self.git('for-each-ref', '--format=%(refname) %(objectname)').decode()

    @property
    def mutations(self):
        return [c for c in self.calls if c['method'] != 'GET' and c['endpoint'] != 'graphql']

    def __call__(self, command, **kwargs):
        method, endpoint = command[3:5]
        payload = json.loads(kwargs.get('input', '{}'))
        self.calls.append({'method': method, 'endpoint': endpoint, 'payload': payload})
        if self.fault:
            result = self.fault(command, kwargs)
            if result is not None:
                return result
        if endpoint == 'graphql':
            return http_response(command, {'data': {'viewer': {'login': 'fixture', 'id': 'fixture-user'},
                'repository': {'nameWithOwner': 'sample/repo', 'databaseId': 123,
                    'viewerPermission': 'WRITE', 'defaultBranchRef': {'name': 'dev', 'target': {'oid': self.git('rev-parse', 'refs/heads/dev').decode().strip()}}}}})
        if endpoint == 'repos/sample/repo':
            return http_response(command, {'id': 123, 'full_name': 'sample/repo', 'private': True})
        if '/git/ref/heads/' in endpoint:
            sha = self.git('rev-parse', 'refs/heads/' + endpoint.split('/git/ref/heads/')[1]).decode().strip()
            return http_response(command, {'object': {'sha': sha, 'type': 'commit'}})
        if method == 'GET' and '/git/refs/heads/' in endpoint:
            ref = 'refs/heads/' + endpoint.split('/git/refs/heads/')[1]
            found = self.git('show-ref', '--verify', '--hash', ref, check=False)
            if found.returncode:
                return http_response(command, {'message': 'synthetic absence'}, 404)
        if method == 'POST' and endpoint.endswith('/git/refs'):
            if self.before_create:
                callback, self.before_create = self.before_create, None
                callback()
            result = self.git('update-ref', payload['ref'], payload['sha'], '0' * 40, check=False)
            if result.returncode:
                return http_response(command, {'message': 'synthetic conflict'}, 422)
            if self.after_create:
                return self.after_create(command, kwargs)
            return http_response(command, {'ref': payload['ref'], 'object': {'sha': payload['sha'], 'type': 'commit'}}, 201)
        result = super().__call__([part for part in command if part != '--include'], **kwargs)
        value = json.loads(result.stdout)
        if '/git/refs/heads/' in endpoint:
            return scoped_response(command, value, result.returncode)
        status = 201 if method == 'POST' else 200
        if result.returncode:
            status = 422
        return http_response(command, value, status, result.returncode)
