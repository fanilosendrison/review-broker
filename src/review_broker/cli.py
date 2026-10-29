"""Universal requester CLI and trusted workflow entry points."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .bounded_preflight import add_bounded_preflight_arguments, run_bounded_preflight_command
from .codex import invoke_once, preflight_codex_runtime
from .evidence import quarantine_contaminated_evidence
from .codespace import CodespaceController
from .execution_recovery import (
    capture_terminal_transition,
    finalize_durable_evidence_artifact,
    mark_ambiguous_execution_indeterminate,
    plan_durable_evidence_artifact,
    record_stopped_transition,
    recover_runtime_evidence,
    stop_and_observe_shutdown,
    workflow_context,
)
from .github_journal import GitHubRefJournal
from .identity import canonical_bytes
from .orchestration import prepare_issue, publish_validated_result
from .reconciliation import reconcile_repository
from .packets import verify_packet
from .pilot_synthetic import run_synthetic_pilot, run_synthetic_pilot_02
from .pilot03_authorization import load_execution_authorization
from .pilot03_controller import run_pilot03_controller
from .pilot03_synthetic import run_synthetic_pilot_03
from .pilot03_transport import Pilot03CodespaceTransport
from .pilot04_controller import run_pilot04_controller
from .pilot04_synthetic import run_synthetic_pilot_04
from .pilot05_controller import run_pilot05_controller
from .pilot05_synthetic import run_synthetic_pilot_05
from .pilot_runtime_config import RB03_RUNTIME, RB04_RUNTIME, RB05_RUNTIME
from .queue import AttemptState
from .requester import CliError, request as _request, result as _result, status as _status
from .reviewer_profile import install_reviewer_profile, reviewer_home_from_environment
from .security_probe import run_installed_reviewer_isolation_probe
from .validation import validate_evidence

DEFAULT_BROKER_REPOSITORY = "fanilosendrison/review-broker"


def _add_pilot_controller(subcommands, name: str):
    controller = subcommands.add_parser(name)
    controller.add_argument("--execution-authorization", type=Path)
    controller.add_argument("--source-sha", required=True)
    controller.add_argument("--broker-wheel", required=True, type=Path)
    controller.add_argument("--codespace", required=True)
    controller.add_argument("--ssh-config", required=True, type=Path)
    controller.add_argument("--ssh-host-alias", required=True)
def _run_prepared_controller(args, runtime, controller):
    authorization = load_execution_authorization(args.execution_authorization)
    transport = Pilot03CodespaceTransport(
        args.codespace, args.ssh_host_alias, args.ssh_config, runtime=runtime,
    )
    result = controller(
        authorization=authorization, source_sha=args.source_sha,
        wheel_path=args.broker_wheel, codespace_identity=args.codespace,
        transport=transport,
    )
    print(canonical_bytes(result).decode("utf-8"))
    return 0 if result.get("pilot_acceptance") == "PASS" else 1
def _run_remote_pilot(args, runner):
    result = runner(broker_wheel_sha256=args.broker_wheel_sha256)
    print(canonical_bytes(result).decode("utf-8"))
    return 0 if result.get("pilot_functional") == "PASS" else 1
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reviewctl")
    parser.add_argument(
        "--broker-repo",
        default=os.environ.get("REVIEW_BROKER_REPOSITORY", DEFAULT_BROKER_REPOSITORY),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    pilot = subcommands.add_parser("pilot-synthetic")
    pilot.add_argument("--run-dir", required=True, type=Path)
    pilot.add_argument("--broker-wheel-sha256", required=True)
    pilot.add_argument("--acknowledge-unqualified-pilot", action="store_true")
    pilot_02 = subcommands.add_parser("pilot-synthetic-02")
    pilot_02.add_argument("--broker-wheel-sha256", required=True)
    pilot_02.add_argument("--acknowledge-unqualified-pilot", action="store_true")
    pilot_03 = subcommands.add_parser("pilot-synthetic-03")
    pilot_03.add_argument("--broker-wheel-sha256", required=True)
    _add_pilot_controller(subcommands, "pilot-synthetic-03-controller")
    pilot_04 = subcommands.add_parser("pilot-synthetic-04")
    pilot_04.add_argument("--broker-wheel-sha256", required=True)
    _add_pilot_controller(subcommands, "pilot-synthetic-04-controller")
    pilot_05 = subcommands.add_parser("pilot-synthetic-05")
    pilot_05.add_argument("--broker-wheel-sha256", required=True)
    _add_pilot_controller(subcommands, "pilot-synthetic-05-controller")
    request = subcommands.add_parser("request")
    request.add_argument("--repo", required=True)
    request.add_argument("--pr", required=True, type=int)
    request.add_argument("--profile", required=True)
    request.add_argument("--mission-file", required=True, type=Path)
    status = subcommands.add_parser("status")
    status.add_argument("--request", required=True)
    result = subcommands.add_parser("result")
    result.add_argument("--request", required=True)
    result.add_argument("--json", action="store_true")
    prepare = subcommands.add_parser("internal-prepare")
    prepare.add_argument("--issue", required=True, type=int)
    prepare.add_argument("--output", required=True, type=Path)
    verify = subcommands.add_parser("internal-verify-packet")
    verify.add_argument("--packet-dir", required=True, type=Path)
    verify.add_argument("--expected-packet-id", required=True)

    arm = subcommands.add_parser("internal-arm")
    arm.add_argument("--request", required=True)
    arm.add_argument("--packet-id", required=True)
    install_profile = subcommands.add_parser("internal-install-reviewer-profile")
    install_profile.add_argument("--trusted-workspace", required=True, type=Path)
    install_profile.add_argument("--packet-dir", required=True, type=Path)
    probe_profile = subcommands.add_parser("internal-probe-reviewer-profile")
    probe_profile.add_argument("--trusted-workspace", required=True, type=Path)
    probe_profile.add_argument("--packet-dir", required=True, type=Path)
    probe_profile.add_argument("--codex-runtime-root", required=True, type=Path)
    preflight_runtime = subcommands.add_parser("internal-preflight-codex-runtime")
    preflight_runtime.add_argument("--runtime-root", required=True, type=Path)
    add_bounded_preflight_arguments(subcommands)
    invoke = subcommands.add_parser("internal-invoke")
    invoke.add_argument("--packet-dir", required=True, type=Path)
    invoke.add_argument("--schema", required=True, type=Path)
    invoke.add_argument("--attempt", required=True)
    invoke.add_argument("--packet-id", required=True)
    invoke.add_argument("--broker-wheel-sha256", required=True)
    invoke.add_argument("--trusted-workspace", required=True, type=Path)
    invoke.add_argument("--codex-runtime-root", required=True, type=Path)
    recover = subcommands.add_parser("internal-recover")
    recover.add_argument("--codespace", required=True)
    recover.add_argument("--remote-dir", required=True)
    recover.add_argument("--output", required=True, type=Path)
    recover.add_argument("--request", required=True)
    recover.add_argument("--attempt", required=True)
    quarantine = subcommands.add_parser("internal-quarantine-evidence")
    quarantine.add_argument("--evidence-dir", required=True, type=Path)
    quarantine.add_argument("--request", required=True)
    quarantine.add_argument("--attempt", required=True)
    capture = subcommands.add_parser("internal-capture-terminal")
    capture.add_argument("--packet-dir", required=True, type=Path)
    capture.add_argument("--request", required=True)
    capture.add_argument("--attempt", required=True)
    capture.add_argument("--packet-id", required=True)
    plan_artifact = subcommands.add_parser("internal-plan-evidence-artifact")
    plan_artifact.add_argument("--evidence-dir", required=True, type=Path)
    plan_artifact.add_argument("--output", required=True, type=Path)
    plan_artifact.add_argument("--artifact-name", required=True)
    finalize_artifact = subcommands.add_parser("internal-finalize-evidence-artifact")
    finalize_artifact.add_argument("--plan", required=True, type=Path)
    finalize_artifact.add_argument("--output", required=True, type=Path)
    finalize_artifact.add_argument("--artifact-id", required=True, type=int)
    finalize_artifact.add_argument("--artifact-digest", required=True)
    indeterminate = subcommands.add_parser("internal-mark-indeterminate")
    indeterminate.add_argument("--recovery-manifest", required=True, type=Path)
    indeterminate.add_argument("--request", required=True)
    indeterminate.add_argument("--attempt", required=True)
    validate = subcommands.add_parser("internal-validate")
    validate.add_argument("--packet-dir", required=True, type=Path)
    stop = subcommands.add_parser("internal-stop-codespace")
    stop.add_argument("--codespace", required=True)
    stop.add_argument("--output", required=True, type=Path)
    stop.add_argument("--request", required=True)
    stop.add_argument("--attempt", required=True)
    stopped = subcommands.add_parser("internal-record-stopped")
    stopped.add_argument("--observation", required=True, type=Path)
    stopped.add_argument("--codespace", required=True)
    stopped.add_argument("--request", required=True)
    stopped.add_argument("--attempt", required=True)
    transition = subcommands.add_parser("internal-transition")
    transition.add_argument("--request", required=True)
    transition.add_argument("--state", required=True, choices=[state.value for state in AttemptState])
    transition.add_argument("--evidence", required=True)
    publish = subcommands.add_parser("internal-publish")
    publish.add_argument("--packet-dir", required=True, type=Path)

    reconcile = subcommands.add_parser("internal-reconcile")
    reconcile.add_argument("--codespace", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Do not even transiently consume or suppress a privileged variable in a
    # pilot process: pilot_environment() must reject it before model transport.
    source_token = (
        None if args.command in (
            "pilot-synthetic", "pilot-synthetic-02", "pilot-synthetic-03",
            "pilot-synthetic-03-controller", "pilot-synthetic-04",
            "pilot-synthetic-04-controller", "pilot-synthetic-05",
            "pilot-synthetic-05-controller",
        ) else os.environ.pop("REVIEW_BROKER_SOURCE_TOKEN", None)
    )
    try:
        if args.command == "pilot-synthetic":
            result = run_synthetic_pilot(
                args.run_dir,
                acknowledge_unqualified_pilot=args.acknowledge_unqualified_pilot,
                broker_wheel_sha256=args.broker_wheel_sha256,
            )
            print(canonical_bytes(result).decode("utf-8"))
            return 0 if result.get("pilot_functional") == "PASS" else 1
        if args.command == "pilot-synthetic-02":
            result = run_synthetic_pilot_02(
                acknowledge_unqualified_pilot=args.acknowledge_unqualified_pilot,
                broker_wheel_sha256=args.broker_wheel_sha256,
            )
            print(canonical_bytes(result).decode("utf-8"))
            return 0 if result.get("pilot_functional") == "PASS" else 1
        if args.command == "pilot-synthetic-03":
            return _run_remote_pilot(args, run_synthetic_pilot_03)
        if args.command == "pilot-synthetic-03-controller":
            return _run_prepared_controller(args, RB03_RUNTIME, run_pilot03_controller)
        if args.command == "pilot-synthetic-04":
            return _run_remote_pilot(args, run_synthetic_pilot_04)
        if args.command == "pilot-synthetic-04-controller":
            return _run_prepared_controller(args, RB04_RUNTIME, run_pilot04_controller)
        if args.command == "pilot-synthetic-05":
            return _run_remote_pilot(args, run_synthetic_pilot_05)
        if args.command == "pilot-synthetic-05-controller":
            return _run_prepared_controller(args, RB05_RUNTIME, run_pilot05_controller)
        if args.command == "request":
            return _request(args)
        if args.command == "status":
            return _status(args)
        if args.command == "result":
            return _result(args)
        if args.command == "internal-prepare":
            value = prepare_issue(
                args.broker_repo,
                args.issue,
                args.output,
                source_token=source_token,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-verify-packet":
            observed = verify_packet(args.packet_dir)
            if observed["packet_id"] != args.expected_packet_id:
                raise CliError("PACKET_ID_MISMATCH")
            return 0
        if args.command == "internal-arm":
            journal = GitHubRefJournal(args.broker_repo)
            journal.transition(args.request, AttemptState.ARMED, [args.packet_id])
            journal.record_invocation(args.request)
            return 0
        if args.command == "internal-install-reviewer-profile":
            home = reviewer_home_from_environment(dict(os.environ))
            install_reviewer_profile(home, args.trusted_workspace, args.packet_dir)
            return 0
        if args.command == "internal-probe-reviewer-profile":
            receipt = run_installed_reviewer_isolation_probe(
                args.trusted_workspace, args.packet_dir, args.codex_runtime_root,
                environment=dict(os.environ),
            )
            print(canonical_bytes(receipt).decode("utf-8"))
            return 0
        if args.command == "internal-preflight-codex-runtime":
            receipt = preflight_codex_runtime(args.runtime_root)
            print(canonical_bytes(receipt).decode("utf-8"))
            return 0
        if args.command == "internal-bounded-v1-preflight":
            print(canonical_bytes(run_bounded_preflight_command(args)).decode("utf-8"))
            return 0
        if args.command == "internal-invoke":
            invoke_once(
                args.packet_dir,
                args.schema,
                args.attempt,
                expected_packet_id=args.packet_id,
                broker_wheel_sha256=args.broker_wheel_sha256,
                trusted_workspace=args.trusted_workspace,
                codex_runtime_root=args.codex_runtime_root,
            )
            return 0
        if args.command == "internal-recover":
            value = recover_runtime_evidence(
                CodespaceController(args.codespace),
                args.remote_dir,
                args.output,
                request_id=args.request,
                attempt_id=args.attempt,
                context=workflow_context(os.environ, source="review-workflow-recovery"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-quarantine-evidence":
            print(canonical_bytes(quarantine_contaminated_evidence(
                args.evidence_dir, request_id=args.request, attempt_id=args.attempt,
            )).decode("utf-8"))
            return 0
        if args.command == "internal-capture-terminal":
            value = capture_terminal_transition(
                args.broker_repo,
                args.packet_dir,
                request_id=args.request,
                attempt_id=args.attempt,
                packet_id=args.packet_id,
                context=workflow_context(os.environ, source="review-workflow-capture"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-plan-evidence-artifact":
            value = plan_durable_evidence_artifact(
                args.broker_repo,
                args.evidence_dir,
                args.output,
                artifact_name=args.artifact_name,
                workflow_run_id=os.environ.get("GITHUB_RUN_ID", ""),
                workflow_run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-finalize-evidence-artifact":
            value = finalize_durable_evidence_artifact(
                args.broker_repo,
                args.plan,
                args.output,
                artifact_id=args.artifact_id,
                artifact_digest=args.artifact_digest,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-mark-indeterminate":
            value = mark_ambiguous_execution_indeterminate(
                args.broker_repo,
                args.recovery_manifest,
                request_id=args.request,
                attempt_id=args.attempt,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-validate":
            print(canonical_bytes(validate_evidence(args.packet_dir)).decode("utf-8"))
            return 0
        if args.command == "internal-stop-codespace":
            value = stop_and_observe_shutdown(
                CodespaceController(args.codespace),
                args.output,
                request_id=args.request,
                attempt_id=args.attempt,
                context=workflow_context(os.environ, source="review-workflow-cleanup"),
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-record-stopped":
            value = record_stopped_transition(
                args.broker_repo,
                args.observation,
                request_id=args.request,
                attempt_id=args.attempt,
                codespace_name=args.codespace,
            )
            print(canonical_bytes(value).decode("utf-8"))
            return 0
        if args.command == "internal-transition":
            GitHubRefJournal(args.broker_repo).transition(
                args.request, AttemptState(args.state), [args.evidence]
            )
            return 0
        if args.command == "internal-publish":
            print(canonical_bytes(publish_validated_result(
                args.broker_repo,
                args.packet_dir,
                source_token=source_token,
            )).decode("utf-8"))
            return 0
        if args.command == "internal-reconcile":
            codespace_token = os.environ.get("REVIEW_BROKER_CODESPACE_TOKEN")
            if not codespace_token:
                raise CliError("CODESPACE_CREDENTIAL_MISSING")
            codespace_environment = dict(os.environ)
            codespace_environment["GH_TOKEN"] = codespace_token
            codespace_environment.pop("GITHUB_TOKEN", None)
            result = reconcile_repository(
                args.broker_repo,
                args.codespace,
                codespace_environment=codespace_environment,
                source_token=source_token,
            )
            print(canonical_bytes(result).decode("utf-8"))
            if any(
                item.get("outcome") == "INFRASTRUCTURE_INCIDENT"
                for item in result
            ):
                return 1
            return 0
    except Exception as exc:  # CLI boundary converts typed failures into a non-secret status.
        print(f"REVIEWCTL_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
