"""Trusted Actions use case: reserve first, read authoritative state, then mint workload proof."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any, Mapping
import urllib.parse
import urllib.request

from .arm_authority_contract import (
    ArmAuthorityError, TRUSTED_REF, WORKFLOW_PATH, envelope_audience, execution_metadata,
)
from .armament import check_prepared_capacity
from .codex_policy import CodexPolicy
from .github_journal import GitHubRefJournal
from .identity import artifact_identity, canonical_bytes
from .input_capacity import assess_packet_capacity
from .queue import AttemptState

# Any represents canonical JSON, validated before requesting issuer authority.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ArmAuthorityError('ARM_TOKEN_REDIRECT_REFUSED')


def actions_token(audience: str, environment: Mapping[str, str]) -> str:
    try:
        url = environment['ACTIONS_ID_TOKEN_REQUEST_URL']
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'pipelines.actions.githubusercontent.com'
            or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment):
            raise ValueError
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if any(k == 'audience' for k, _ in query):
            raise ValueError
        query.append(('audience', audience))
        target = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        request = urllib.request.Request(target, headers={
            'Authorization': 'Bearer ' + environment['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=15) as response:
            raw = response.read(65_537)
            if len(raw) > 65_536:
                raise ValueError
        token = json.loads(raw)['value']
        if not isinstance(token, str) or not token or len(token) > 32_768:
            raise ValueError
        return token
    except Exception as exc:
        raise ArmAuthorityError('ARM_ACTIONS_OIDC_UNAVAILABLE') from exc


def arm_and_authorize(
    *, journal: GitHubRefJournal, packet_directory: Path, request_id: str, packet_id: str,
    codespace_name: str, codespace_id: str, authorization_file: Path,
    environment: Mapping[str, str] = os.environ,
) -> dict[str, str]:
    """A different process cannot authorize itself merely by observing ARMED/count-one."""
    repository, sha = environment['GITHUB_REPOSITORY'], environment['GITHUB_SHA']
    metadata, raw_metadata = execution_metadata(packet_directory)
    if (environment.get('GITHUB_ACTIONS') != 'true' or journal.repository != repository
        or metadata['broker_repository'] != repository
        or environment['GITHUB_REF'] != TRUSTED_REF
        or environment['GITHUB_WORKFLOW_REF'] != repository + '/' + WORKFLOW_PATH + '@' + TRUSTED_REF
        or environment['GITHUB_WORKFLOW_SHA'] != sha):
        raise ArmAuthorityError('ARM_ACTIONS_CONTEXT_INVALID')
    if authorization_file.resolve().is_relative_to(packet_directory.resolve()):
        raise ArmAuthorityError('ARM_AUTHORIZATION_MUST_BE_OUTSIDE_PACKET')
    # Exclusive private output: no overwrite or ambiguous recovery, even before ARM.
    fd = os.open(authorization_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        receipt = check_prepared_capacity(journal=journal, packet_directory=packet_directory,
            request_id=request_id, packet_id=packet_id, executing_broker_sha=sha, arm=True)
        commit, reserved = journal.get_snapshot(request_id)
        manifest, observed = assess_packet_capacity(packet_directory, request_id=request_id,
            packet_id=packet_id, attempt_id=reserved.attempt_id, executing_broker_sha=sha)
        if (reserved.state is not AttemptState.ARMED or reserved.invocation_count != 1
            or reserved.input_capacity != receipt or observed != receipt
            or artifact_identity(canonical_bytes(manifest)) not in reserved.evidence_ids):
            raise ArmAuthorityError('ARM_RESERVATION_NOT_OBSERVED')
        envelope = dict(schema_version=1, authorization_id=secrets.token_hex(32),
            broker_repository=repository, broker_repository_id=environment['GITHUB_REPOSITORY_ID'],
            executing_broker_sha=sha, workflow_ref=environment['GITHUB_WORKFLOW_REF'],
            workflow_sha=environment['GITHUB_WORKFLOW_SHA'], ref=environment['GITHUB_REF'],
            run_id=environment['GITHUB_RUN_ID'], run_attempt=environment['GITHUB_RUN_ATTEMPT'],
            journal_commit_sha=commit, request_id=request_id, attempt_id=reserved.attempt_id,
            packet_id=packet_id, input_sha256=receipt['input_sha256'],
            broker_metadata_sha256=hashlib.sha256(raw_metadata).hexdigest(),
            capacity_receipt=receipt, reviewer_policy=asdict(CodexPolicy()),
            codespace_name=codespace_name, codespace_id=codespace_id)
        audience = envelope_audience(envelope)
        token = actions_token(audience, environment)
        if journal.get_snapshot(request_id) != (commit, reserved):
            raise ArmAuthorityError('ARM_RESERVATION_CHANGED')
        stream.write(canonical_bytes({'envelope': envelope, 'jwt': token}) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(authorization_file.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'authorization_audience': audience, 'journal_commit_sha': commit}
