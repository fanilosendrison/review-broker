"""Real Git object/ref transport fixture for deterministic journal CAS schedules."""
import base64
import json
import os
from pathlib import Path
import subprocess

from review_broker.identity import canonical_bytes
from tests.journal_http_response import scoped_response


class JournalGitTransport:
    """Implement GitHub's relevant Git-data operations using real local Git."""

    def __init__(self, root: Path):
        self.root = root
        self.env = {k: v for k, v in os.environ.items() if k in {'PATH', 'SYSTEMROOT'}}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='test@example.invalid',
                        GIT_AUTHOR_DATE='2000-01-01T00:00:00+00:00',
                        GIT_COMMITTER_DATE='2000-01-01T00:00:00+00:00',
                        GIT_INDEX_FILE=str(root / 'fixture-index'))
        self.git('init', '--bare', '-q', str(root))
        self.base_tree = self.git('mktree', data=b'').strip().decode()
        self.before_patch = None
        self.proposals = []
        self.noops = 0
        self.patch_count = 0
        self.ignore_update = False
        self.malformed_update = False

    def git(self, *args, data=None, check=True):
        p = subprocess.run(['git', '--git-dir', str(self.root), *args], input=data,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env,
                           check=False)
        if check and p.returncode:
            raise AssertionError(p.stderr.decode())
        return p.stdout if check else p

    def seed(self, record, ref):
        encoded = base64.b64encode(canonical_bytes(record.as_dict()) + b'\n').decode()
        blob = self.blob(encoded)
        tree = self.tree(self.base_tree, blob)
        sha = self.commit(tree, [], 'seed')
        self.git('update-ref', ref, sha)
        return sha

    def blob(self, encoded):
        return self.git('hash-object', '-w', '--stdin', data=base64.b64decode(encoded)).strip().decode()

    def tree(self, base, blob):
        self.git('read-tree', base)
        self.git('update-index', '--add', '--cacheinfo',
                 '100644,' + blob + ',.review-broker/attempt.json')
        return self.git('write-tree').strip().decode()

    def commit(self, tree, parents, message):
        args = ['commit-tree', tree]
        for parent in parents:
            args.extend(['-p', parent])
        return self.git(*args, data=message.encode()).strip().decode()

    def __call__(self, command, **kwargs):
        method, endpoint = command[3:5]
        payload = json.loads(kwargs.get('input', '{}'))
        def result(value, code=0):
            if '--include' in command:
                return scoped_response(command, value, code)
            return subprocess.CompletedProcess(command, code, json.dumps(value), '')
        if '/contents/' in endpoint:
            sha = endpoint.split('?ref=')[1]
            raw = self.git('show', sha + ':.review-broker/attempt.json')
            return result({'encoding': 'base64', 'content': base64.b64encode(raw).decode()})
        if method == 'GET' and '/git/commits/' in endpoint:
            tree = self.git('show', '-s', '--format=%T', endpoint.rsplit('/', 1)[1]).strip().decode()
            return result({'tree': {'sha': tree}})
        if method == 'POST' and endpoint.endswith('/git/blobs'):
            return result({'sha': self.blob(payload['content'])})
        if method == 'POST' and endpoint.endswith('/git/trees'):
            return result({'sha': self.tree(payload['base_tree'], payload['tree'][0]['sha'])})
        if method == 'POST' and endpoint.endswith('/git/commits'):
            sha = self.commit(payload['tree'], payload['parents'], payload['message'])
            self.proposals.append(sha)
            return result({'sha': sha})
        if '/git/refs/heads/' in endpoint:
            ref = 'refs/heads/' + endpoint.split('/git/refs/heads/')[1]
            current = self.git('rev-parse', ref).strip().decode()
            if method == 'GET':
                return result({'object': {'sha': current}})
            assert method == 'PATCH' and payload['force'] is False
            self.patch_count += 1
            callback, self.before_patch = self.before_patch, None
            if callback:
                callback()
            current = self.git('rev-parse', ref).strip().decode()
            proposed = payload['sha']
            if self.ignore_update:
                return result({'object': {'sha': proposed}})
            ancestor = self.git('merge-base', '--is-ancestor', current, proposed, check=False)
            if ancestor.returncode:
                return result({'message': 'not a fast forward'}, 1)
            if proposed == current:
                self.noops += 1
            self.git('update-ref', ref, proposed, current)
            return result({} if self.malformed_update else {'object': {'sha': proposed}})
        raise AssertionError((method, endpoint))
