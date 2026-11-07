"""Internal pre-model CLI registration and sanitized dependency selection only."""
from dataclasses import asdict
import os
from pathlib import Path
import tempfile


def add_v3_commands(subcommands):
    for command in ('internal-v3-pre-model-controller','internal-v3-controller-start-gate'):
        parser=subcommands.add_parser(command)
        parser.add_argument('--issue',required=True,type=int)
        parser.add_argument('--request-id',required=True)
    for command in ('internal-v3-pre-model-worker','internal-v3-wait-dispatch-ack'):
        parser=subcommands.add_parser(command)
        parser.add_argument('--request-id',required=True)
        parser.add_argument('--reservation-id',required=True)
        parser.add_argument('--generation',required=True,type=int)


def run_v3_command(args,source_token):
    # Lazy selection keeps the legacy v1/v2 command/import path separate from
    # operational v3 providers. No reviewed content can select these dependencies.
    from .github_http_live_v3 import urllib_executor
    from .github_live_runtime_v3 import ProtectedCheckoutV3,GitHubActionsRuntimeBoundaryV3,exact_positive,REPOSITORY
    from .github_actions_controller_authority_v3 import GATES,require_owner_gates_v3
    from .identity import canonical_bytes
    try:
        if args.broker_repo!=REPOSITORY:raise ValueError('V3_BROKER_REPOSITORY_FIXED')
        environment=dict(os.environ)
        token=environment['GITHUB_TOKEN']
        checkout=ProtectedCheckoutV3.observe(Path.cwd(),environment['GITHUB_SHA'])
        role='controller' if args.command in {'internal-v3-pre-model-controller','internal-v3-controller-start-gate'} else 'worker'
        inputs=({'request_issue_number':args.issue,'request_id':args.request_id} if role=='controller'
                else {'request_id':args.request_id,'reservation_id':args.reservation_id,'generation':args.generation})
        runtime=GitHubActionsRuntimeBoundaryV3(environment=environment,checkout=checkout,role=role,
            inputs=inputs,token=token,executor=urllib_executor)
        if role=='controller':
            from .live_pre_model_controller_v3 import controller_authority_v3,run_live_controller_v3
            gates={key:environment.get(key) for key in GATES}
            if args.command=='internal-v3-controller-start-gate':
                from .github_journal_transport_v3 import ReadStatusV3
                controller_authority_v3(runtime,args.issue,args.request_id,gates)
                # Only the observer factory is used. No source, ticket or writer.
                from .live_journal_composition_v3 import live_journal_v3,GitHubOriginalAdmissionAuthorityV3
                def deny():raise ValueError('CONTROLLER_START_GATE_READ_ONLY')
                journal=live_journal_v3(runtime,GitHubOriginalAdmissionAuthorityV3(runtime.api),write_guard=deny)
                read=journal.transport.read_claim(journal.claim_ref(args.request_id))
                if source_token is not None or read.status is not ReadStatusV3.MISSING:
                    raise ValueError('CONTROLLER_START_GATE_NOT_INITIAL')
                print(canonical_bytes({'CONTROLLER_START_GATE':'ACCEPTED'}).decode());return 0
            private=Path(tempfile.mkdtemp(prefix='rb-v3-controller-'))
            result=run_live_controller_v3(runtime=runtime,issue=args.issue,request_id=args.request_id,
                gates=gates,source_token=source_token,app_slug=environment['REVIEW_BROKER_SOURCE_APP_SLUG'],
                installation_id=exact_positive(environment['REVIEW_BROKER_SOURCE_INSTALLATION_ID']),
                private_root=private,source_executor=urllib_executor)
            print(canonical_bytes({'status':result.status.value,'reason':result.reason}).decode())
            return 0 if result.status.value=='DISPATCH_ACKNOWLEDGED' else 1
        from .live_pre_model_worker_v3 import worker_observer_v3,run_live_worker_v3
        from .pre_model_ack_start_gate_v3 import wait_dispatch_ack_v3
        context=runtime.worker_context()
        if args.command=='internal-v3-wait-dispatch-ack':
            if source_token is not None:raise ValueError('ACK_GATE_SOURCE_CREDENTIAL_FORBIDDEN')
            journal,dispatch=worker_observer_v3(runtime)
            result=wait_dispatch_ack_v3(journal=journal,runtime=runtime,inputs=context.inputs,dispatch_authority=dispatch)
            if result.accepted:
                original=journal.read(args.request_id).record.attempt.admission
                body=journal.admission_authority.origin(original)
                require_owner_gates_v3({k:environment.get(k) for k in GATES},sha=checkout.sha,
                    request_id=args.request_id,issue=original['origin_observation']['issue_number'],body=body)
            print(canonical_bytes({'ACK_GATE':'ACCEPTED' if result.accepted else 'REJECTED','reason':result.reason}).decode())
            return 0 if result.accepted else 1
        node=Path(environment['REVIEW_BROKER_NODE_EXECUTABLE'])
        if not node.is_absolute():raise ValueError('NODE24_LAUNCHER_EXECUTABLE_REQUIRED')
        private=Path(tempfile.mkdtemp(prefix='rb-v3-worker-'))
        result=run_live_worker_v3(runtime=runtime,source_token=source_token,
            app_slug=environment['REVIEW_BROKER_SOURCE_APP_SLUG'],
            installation_id=exact_positive(environment['REVIEW_BROKER_SOURCE_INSTALLATION_ID']),private_root=private,
            helper_root=Path(environment['REVIEW_BROKER_ARTIFACT_HELPER_ROOT']),node=node,
            artifact_environment=environment,source_executor=urllib_executor)
        print(canonical_bytes(asdict(result)).decode())
        return 0 if result.state=='PREPARED' and result.cold_verified else 1
    except Exception as error:
        print(canonical_bytes({'status':'REJECTED','reason':'PREMODEL_COMPOSITION_UNCONFIRMED',
            'error_type':type(error).__name__}).decode())
        return 1
