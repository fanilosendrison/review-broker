"""One provider-only dispatch to the exact inert default Worker stub; never a broker run."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess

from review_broker.github_actions_dispatch_provider_v3 import (
    classify_dispatch_response_v3, dispatch_transport_observation_v3,
    workflow_dispatch_payload_v3,
)
from review_broker.github_live_runtime_v3 import LiveGitHubApiV3, REPOSITORY, REPOSITORY_ID, OWNER_ID, WORKER_PATH, CONTROLLER_PATH
from review_broker.identity import canonical_bytes
from review_broker.pre_model_dispatch_v3 import InitialDispatchStatusV3

# SHA256 of the owner-qualified PR92 stub, not the active broker Worker.
STUB_SHA256 = '39e98c2a59a9a058c4f5e5226aeed04f0878d9b998f76b6bb4f10345a02734a4'
PROBE_REQUEST = 'qualification-only-issue70-dispatch-provider-probe'
PROBE_RESERVATION = 'qualification-only-no-review-broker-reservation'
PROBE_JOB = 'dispatch-provider-probe'


def require_context(environment, caller_sha, caller_ref):
    if (re.fullmatch('[0-9a-f]{40}', caller_sha) is None
            or not caller_ref.startswith('refs/heads/qualification/issue70-dispatch-provider-')
            or environment.get('GITHUB_REPOSITORY') != REPOSITORY
            or environment.get('GITHUB_REPOSITORY_ID') != str(REPOSITORY_ID)
            or environment.get('GITHUB_SHA') != caller_sha
            or environment.get('GITHUB_WORKFLOW_SHA') != caller_sha
            or environment.get('GITHUB_REF') != caller_ref
            or environment.get('GITHUB_WORKFLOW_REF') != f'{REPOSITORY}/{CONTROLLER_PATH}@{caller_ref}'
            or environment.get('GITHUB_JOB') != PROBE_JOB
            or environment.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or environment.get('GITHUB_RUN_ATTEMPT') != '1'
            or environment.get('GITHUB_ACTOR_ID') != str(OWNER_ID)):
        raise ValueError('INERT_PROBE_CONTEXT_REJECTED')


def require_inert_target(api, dev_sha):
    if re.fullmatch('[0-9a-f]{40}', dev_sha) is None:
        raise ValueError('INERT_PROBE_DEV_IDENTITY_INVALID')
    repository = api.get('')
    if (repository.get('id') != REPOSITORY_ID or repository.get('full_name') != REPOSITORY
            or repository.get('default_branch') != 'dev'):
        raise ValueError('INERT_PROBE_REPOSITORY_CHANGED')
    workflow = api.get('/actions/workflows/410394071')
    if workflow.get('id') != 410394071 or workflow.get('path') != WORKER_PATH or workflow.get('state') != 'active':
        raise ValueError('INERT_PROBE_WORKFLOW_CHANGED')
    ref = api.get('/git/ref/heads/dev')
    if ref.get('ref') != 'refs/heads/dev' or ref.get('object', {}).get('sha') != dev_sha:
        raise ValueError('INERT_PROBE_DEV_MOVED')
    source = api.get('/contents/' + WORKER_PATH + '?ref=' + dev_sha)
    if source.get('type') != 'file' or source.get('encoding') != 'base64':
        raise ValueError('INERT_PROBE_STUB_UNAVAILABLE')
    raw = base64.b64decode(''.join(source['content'].splitlines()), validate=True)
    if hashlib.sha256(raw).hexdigest() != STUB_SHA256:
        raise ValueError('INERT_PROBE_STUB_CHANGED')
    return {'workflow_id': 410394071, 'ref': 'dev', 'head_sha': dev_sha,
            'stub_sha256': STUB_SHA256}


def run_probe(api, environment, *, caller_sha, caller_ref, dev_sha):
    """One invocation only; post-call uncertainty is never another opportunity."""
    require_context(environment, caller_sha, caller_ref)
    run_id = environment.get('GITHUB_RUN_ID', '')
    if re.fullmatch('[1-9][0-9]*', run_id) is None:
        raise ValueError('INERT_PROBE_RUN_ID_INVALID')
    run = api.get('/actions/runs/' + run_id)
    if (run.get('id') != int(run_id) or run.get('workflow_id') != 410394070
            or run.get('path') != CONTROLLER_PATH or run.get('event') != 'workflow_dispatch'
            or type(run.get('run_attempt')) is not int or run.get('run_attempt') != 1
            or run.get('head_sha') != caller_sha
            or run.get('head_branch') != caller_ref.removeprefix('refs/heads/')
            or run.get('actor', {}).get('id') != OWNER_ID
            or run.get('triggering_actor', {}).get('id') != OWNER_ID
            or run.get('status') != 'in_progress'):
        raise ValueError('INERT_PROBE_CALLER_UNRECOGNIZED')
    target = require_inert_target(api, dev_sha)
    jobs = api.metadata.listing('/actions/runs/' + run_id + '/attempts/1/jobs', {}, 'jobs', api.guard)
    if (len(jobs) != 1 or jobs[0].get('name') != PROBE_JOB
            or jobs[0].get('head_sha') != caller_sha
            or jobs[0].get('run_id') != int(run_id)
            or type(jobs[0].get('run_attempt')) is not int or jobs[0].get('run_attempt') != 1
            or jobs[0].get('status') != 'in_progress'):
        raise ValueError('INERT_PROBE_JOB_UNRECOGNIZED')
    payload = workflow_dispatch_payload_v3(execution_ref='refs/heads/dev',
        request_id=PROBE_REQUEST, reservation_id=PROBE_RESERVATION, generation=1)
    # Final fresh target confrontation immediately before the sole mutation.
    require_inert_target(api, dev_sha)
    context = dict(workflow_path=WORKER_PATH, execution_ref='refs/heads/dev',
        request_id=PROBE_REQUEST, reservation_id=PROBE_RESERVATION, generation=1)
    try:
        response = api.post_dispatch(payload)
        result, observation = classify_dispatch_response_v3(response, **context)
        observed = result.status is InitialDispatchStatusV3.OBSERVED
    except Exception as error:
        observation = dispatch_transport_observation_v3(error, **context)
        observed = False
    return {'schema_version': 1, 'qualification_only': True, 'caller_sha': caller_sha,
            'target': target, 'post_invocations': 1, 'provider_observation': observation.as_dict(),
            'dispatch_observed': observed,
            'verified_run_url': (f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{observation.recognized_run_id}'
                                 if observed else None),
            'verified_html_url': (f'https://github.com/{REPOSITORY}/actions/runs/{observation.recognized_run_id}'
                                  if observed else None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caller-sha', required=True)
    parser.add_argument('--caller-ref', required=True)
    parser.add_argument('--dev-sha', required=True)
    args = parser.parse_args()
    environment = dict(os.environ)
    try:
        require_context(environment, args.caller_sha, args.caller_ref)
        checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).removesuffix('\n')
        if checkout != args.caller_sha:
            raise ValueError('INERT_PROBE_CHECKOUT_MISMATCH')
        # Only the job-scoped credential explicitly mapped by the pinned workflow.
        # Never resolve an ambient personal credential or source-App credential.
        api = LiveGitHubApiV3(environment['GITHUB_TOKEN'], guard=lambda: require_context(
            environment, args.caller_sha, args.caller_ref))
        value = run_probe(api, environment, caller_sha=args.caller_sha,
                          caller_ref=args.caller_ref, dev_sha=args.dev_sha)
        print(canonical_bytes(value).decode())
        return 0 if value['dispatch_observed'] else 1
    except Exception:
        print(canonical_bytes({'status': 'PROBE_REFUSED', 'error_class': 'LOCAL_PREFLIGHT_UNCONFIRMED'}).decode())
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
